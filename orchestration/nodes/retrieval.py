"""Nó: retrieve_threats — recupera ameaças canônicas do KG para um componente.

Política de erro (deliberada — distingue falha semântica de falha de infra):
1. `knowledge.query.get_stride_threats()` — implementação real (Dev 2).
2. `ImportError`/`NotImplementedError` → fallback para
   `knowledge.fixtures.get_fixture_for(element_type)` (mock de contrato, usado
   só enquanto Dev 2 não publicou a query real).
3. `ElementTypeNotFoundError` (o tipo não existe na taxonomia) → WARNING +
   KGQueryResult vazio e **segue**. É caso semântico esperado, por-componente:
   abortar a análise toda porque 1 de N componentes tem tipo desconhecido seria
   frágil.
4. **Qualquer outra falha (Neo4j fora do ar, timeout, auth...) NÃO é capturada:**
   propaga e vira `status="error"` no `service.py`. Falha de infra é sistêmica
   (afeta todos os componentes) — travar cedo evita gastar ~28k tokens de LLM
   produzindo um relatório sem grounding que mascara a base indisponível.

O desenfileiramento (pop + localizar Component) é lógica real desde o Épico 1.
"""
from __future__ import annotations

import logging

from knowledge.exceptions import ElementTypeNotFoundError
from knowledge.models import KGQueryResult
from orchestration.state import GraphState

logger = logging.getLogger(__name__)


def _fetch_kg_result(component) -> KGQueryResult:
    # Imports dentro da função: captura ImportError de um módulo que pode ainda
    # não existir e evita acoplar orchestration/ a knowledge.query no import.
    try:
        from knowledge.query import get_stride_threats

        return get_stride_threats(
            element_type=component.element_type,
            cloud_service=component.aws_service,
        )
    except (ImportError, NotImplementedError):
        logger.info(
            "Retrieval fallback to fixture — knowledge.query.get_stride_threats "
            "ainda não disponível (component=%s)",
            component.name,
        )
        from knowledge.fixtures import get_fixture_for

        return get_fixture_for(component.element_type)
    except ElementTypeNotFoundError:
        logger.warning(
            "KG query — element type not found: %s", component.element_type
        )
        return KGQueryResult(
            element_type=component.element_type,
            cloud_service=component.aws_service,
            stride_results=[],
            total_threats=0,
            query_source="taxonomy",
        )


def retrieve_threats(state: GraphState) -> dict:
    queue = list(state["components_queue"])
    current_id = queue.pop(0)

    component = next(c for c in state["diagram"].components if c.id == current_id)

    kg_result = _fetch_kg_result(component)

    kg_results = {**state["kg_results"], current_id: kg_result}

    logger.info(
        "Retrieval completed — component=%s element_type=%s service=%s threats=%d source=%s",
        component.name,
        component.element_type,
        component.aws_service,
        kg_result.total_threats,
        kg_result.query_source,
    )

    return {
        "current_component_id": current_id,
        "components_queue": queue,
        "kg_results": kg_results,
    }
