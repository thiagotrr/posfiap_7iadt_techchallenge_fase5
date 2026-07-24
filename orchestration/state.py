"""Estado do grafo LangGraph (TypedDict, padrão LangGraph — não Pydantic).

`GraphState` é o dicionário Python passado entre os nós do grafo. Os modelos
Pydantic (ComponentAnalysis, STRIDEReport) são usados como *valores* dentro do
estado, mas o container é um TypedDict conforme convenção do LangGraph.

Sem dependência de `langgraph` aqui — apenas os tipos.
"""
from __future__ import annotations

from typing import Optional, TypedDict

from extraction.schemas import ArchitectureDiagram
from knowledge.models import KGQueryResult

# Import em runtime (não sob TYPE_CHECKING): o LangGraph chama
# get_type_hints(GraphState) ao montar StateGraph(GraphState), e todas as
# anotações são strings por causa de `from __future__ import annotations`.
# Se estes nomes não existirem em runtime, get_type_hints() levanta NameError.
# Não há import circular — orchestration.models só depende de pydantic.
from orchestration.models import ComponentAnalysis, STRIDEReport


class GraphState(TypedDict):
    """Estado compartilhado entre os nós do grafo de análise STRIDE."""

    diagram: ArchitectureDiagram
    components_queue: list[str]
    current_component_id: Optional[str]
    kg_results: dict[str, KGQueryResult]
    component_analyses: dict[str, ComponentAnalysis]
    # Componentes cuja geração caiu no fallback (stride_entries=[] por falha) —
    # distingue "falha" de "sem ameaças" no components_failed_count do contrato.
    failed_component_ids: list[str]
    chat_history: list[dict]
    hitl_feedback: Optional[str]
    hitl_approved: bool
    report: Optional[STRIDEReport]
    error: Optional[str]
