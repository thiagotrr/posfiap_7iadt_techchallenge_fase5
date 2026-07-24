"""Arestas condicionais do grafo.

`check_iteration` decide se há mais componentes a processar (volta ao retrieval)
ou se a iteração terminou (segue para o HITL). `route_after_hitl` decide, após
a revisão HITL, entre refinar ou gerar o relatório.

Funções de aresta condicional NÃO mutam o estado — apenas retornam a chave de
roteamento (string). O desenfileiramento acontece em retrieve_threats.
"""
from __future__ import annotations

import logging

from orchestration.state import GraphState

logger = logging.getLogger(__name__)


def check_iteration(state: GraphState) -> str:
    if state["components_queue"]:
        return "retrieve_threats"
    logger.info(
        "check_iteration: fila vazia, %d componentes analisados",
        len(state["component_analyses"]),
    )
    return "hitl_review"


def route_after_hitl(state: GraphState) -> str:
    if state["hitl_approved"]:
        return "generate_report"
    return "refine_analysis"
