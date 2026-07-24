"""Construção e compilação do grafo LangGraph de análise STRIDE.

`build_graph()` monta a topologia final (a mesma da Semana 2 — só o conteúdo
dos nós é mock na Semana 1). `get_compiled_graph()` expõe um singleton compilado
com MemorySaver como checkpointer.

Topologia (ver README / mermaid do CLAUDE.md):

    START → prepare_components → retrieve_threats → generate_threats
    generate_threats -[fila não vazia]-> retrieve_threats
    generate_threats -[fila vazia]-> hitl_review
    hitl_review -[approve]-> generate_report
    hitl_review -[refine]-> refine_analysis → hitl_review
    generate_report → END

MemorySaver: suficiente para o MVP acadêmico. AsyncSqliteSaver/RedisSaver
documentados como melhoria futura.
"""
from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from orchestration.nodes import (
    check_iteration,
    generate_report,
    generate_threats,
    hitl_review,
    prepare_components,
    refine_analysis,
    retrieve_threats,
    route_after_hitl,
)
from orchestration.state import GraphState

_compiled_graph: CompiledStateGraph | None = None


def build_graph() -> CompiledStateGraph:
    """Monta e compila o grafo. Cada chamada retorna uma nova instância."""
    builder = StateGraph(GraphState)

    builder.add_node("prepare_components", prepare_components)
    builder.add_node("retrieve_threats", retrieve_threats)
    builder.add_node("generate_threats", generate_threats)
    builder.add_node("hitl_review", hitl_review)
    builder.add_node("refine_analysis", refine_analysis)
    builder.add_node("generate_report", generate_report)

    builder.add_edge(START, "prepare_components")
    builder.add_edge("prepare_components", "retrieve_threats")
    builder.add_edge("retrieve_threats", "generate_threats")

    builder.add_conditional_edges(
        "generate_threats",
        check_iteration,
        {
            "retrieve_threats": "retrieve_threats",
            "hitl_review": "hitl_review",
        },
    )
    builder.add_conditional_edges(
        "hitl_review",
        route_after_hitl,
        {
            "refine_analysis": "refine_analysis",
            "generate_report": "generate_report",
        },
    )

    builder.add_edge("refine_analysis", "hitl_review")
    builder.add_edge("generate_report", END)

    return builder.compile(checkpointer=MemorySaver())


def get_compiled_graph() -> CompiledStateGraph:
    """Singleton do grafo compilado (compartilha o MemorySaver entre chamadas)."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph
