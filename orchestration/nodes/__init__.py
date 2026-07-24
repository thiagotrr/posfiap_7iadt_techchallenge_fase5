"""Nós do grafo de orquestração STRIDE.

Semana 1 (Épico 1): implementações MOCK — topologia final do grafo com conteúdo
determinístico de placeholder, para validar o fluxo end-to-end contra fixtures
antes das integrações reais (Neo4j/LLM) da Semana 2.
"""
from orchestration.nodes.check_iteration import check_iteration, route_after_hitl
from orchestration.nodes.generation import generate_threats
from orchestration.nodes.hitl import hitl_review
from orchestration.nodes.prepare_components import prepare_components
from orchestration.nodes.refine import refine_analysis
from orchestration.nodes.report import generate_report
from orchestration.nodes.retrieval import retrieve_threats

__all__ = [
    "prepare_components",
    "retrieve_threats",
    "generate_threats",
    "check_iteration",
    "route_after_hitl",
    "hitl_review",
    "refine_analysis",
    "generate_report",
]
