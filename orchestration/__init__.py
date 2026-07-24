"""Módulo de orquestração da análise STRIDE (Dev 3).

Ponto de entrada público do contrato. `run_analysis()`/`send_hitl_message()`
(service.py) chegam no Épico 4; por ora exportamos o contrato de dados e a
construção do grafo já disponíveis para o Dev 4.
"""
from orchestration.graph import build_graph, get_compiled_graph
from orchestration.models import (
    ComponentAnalysis,
    GraphStateResponse,
    STRIDEReport,
    STRIDEThreatEntry,
)
from orchestration.service import (
    get_analysis_state,
    run_analysis,
    send_hitl_message,
)
from orchestration.state import GraphState

__all__ = [
    "GraphState",
    "STRIDEThreatEntry",
    "ComponentAnalysis",
    "STRIDEReport",
    "GraphStateResponse",
    "build_graph",
    "get_compiled_graph",
    "run_analysis",
    "send_hitl_message",
    "get_analysis_state",
]
