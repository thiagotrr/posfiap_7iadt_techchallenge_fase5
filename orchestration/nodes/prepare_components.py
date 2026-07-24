"""Nó: prepare_components — inicializa a fila de componentes e os acumuladores.

Ponto de entrada do grafo. Popula `components_queue` a partir do diagrama e
zera os acumuladores de estado. Não é mock: essa lógica é a mesma na Semana 2.
"""
from __future__ import annotations

import logging

from orchestration.state import GraphState

logger = logging.getLogger(__name__)

# Ordem de análise por tipo de elemento: processos primeiro (maior superfície de
# lógica/ataque), depois armazenamentos, fluxos e entidades externas. Tipos fora
# da lista (não esperados, dado o Literal do Dev 1) vão para o fim.
_ELEMENT_TYPE_ORDER = ["process", "data_store", "data_flow", "external_entity"]


def _order_key(element_type: str) -> int:
    try:
        return _ELEMENT_TYPE_ORDER.index(element_type)
    except ValueError:
        return len(_ELEMENT_TYPE_ORDER)


def prepare_components(state: GraphState) -> dict:
    diagram = state["diagram"]
    ordered = sorted(diagram.components, key=lambda c: _order_key(c.element_type))
    queue = [component.id for component in ordered]

    logger.info(
        "Analysis prepared — total_components=%d order=%s",
        len(queue),
        [component.element_type for component in ordered],
    )

    return {
        "components_queue": queue,
        "current_component_id": None,
        "kg_results": {},
        "component_analyses": {},
        "failed_component_ids": [],
        "chat_history": [],
        "hitl_feedback": None,
        # Épico 3: o grafo pausa no hitl_review (interrupt) e a aprovação é
        # decidida pela retomada do usuário. Inicia False (não aprovado); o
        # hitl_review sobrescreve conforme a decisão via Command(resume=...).
        "hitl_approved": False,
        "report": None,
        "error": None,
    }
