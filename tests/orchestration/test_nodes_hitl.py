"""Testes do HITL real — interrupt()/Command(resume=) (US-3.1, Épico 3).

Dirige o grafo compilado: invoca (pausa no hitl_review) e retoma com uma decisão.
LLM mockado (autouse) — nenhuma chamada real de rede.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from langgraph.types import Command

from extraction.schemas import (
    ArchitectureDiagram,
    Component,
    DataFlow,
    DiagramMetadata,
    TrustBoundary,
)
from orchestration.graph import build_graph
from orchestration.llm_client import LLMAnalysisClient

_MOCK_LLM_JSON = json.dumps(
    [
        {
            "category": "S",
            "threat_name": "[MOCK] Spoofing",
            "threat_description": "Ameaça mock.",
            "severity": "medium",
            "mitigations": ["m"],
            "source": "llm_only",
        }
    ]
)


@pytest.fixture(autouse=True)
def _mock_llm_analyze():
    with patch.object(LLMAnalysisClient, "analyze", return_value=_MOCK_LLM_JSON):
        yield


def _diagram(n: int = 2) -> ArchitectureDiagram:
    return ArchitectureDiagram(
        diagram_metadata=DiagramMetadata(
            cloud_provider="aws", region=None, extraction_confidence="alta"
        ),
        trust_boundaries=[TrustBoundary(id="tb", name="B", type="vpc", parent=None)],
        components=[
            Component(
                id=f"c{i}", name=f"Comp {i}", aws_service="Lambda",
                element_type="process", category=None, trust_boundary="tb",
                instance_count=1,
            )
            for i in range(1, n + 1)
        ],
        data_flows=[
            DataFlow(
                id="f1", source="c1", destination="c1", protocol="x",
                crosses_boundary=False, note=None,
            )
        ],
    )


def _cfg(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": 100}


def test_grafo_pausa_no_hitl_com_summary():
    graph = build_graph()
    cfg = _cfg("hitl-pause")
    graph.invoke({"diagram": _diagram(2)}, cfg)

    snap = graph.get_state(cfg)
    assert snap.next == ("hitl_review",)          # pausado, não concluído
    # LangGraph não materializa canais None; report ausente = ainda sem relatório.
    assert snap.values.get("report") is None

    # payload do interrupt disponível para a UI
    interrupts = snap.tasks[0].interrupts
    payload = interrupts[0].value
    assert payload["type"] == "hitl_review"
    assert len(payload["summary"]) == 2           # 2 componentes analisados
    assert payload["summary"][0]["threats_count"] == 1


def test_approve_gera_relatorio():
    graph = build_graph()
    cfg = _cfg("hitl-approve")
    graph.invoke({"diagram": _diagram(2)}, cfg)

    final = graph.invoke(Command(resume={"action": "approve"}), cfg)

    assert graph.get_state(cfg).next == ()        # concluído
    assert final["report"] is not None
    assert final["report"].total_components == 2
    assert final["hitl_approved"] is True


def test_refine_pausa_de_novo_e_depois_aprova():
    graph = build_graph()
    cfg = _cfg("hitl-refine")
    graph.invoke({"diagram": _diagram(1)}, cfg)

    # 1) pede refinamento -> volta a pausar no hitl_review
    graph.invoke(Command(resume={"action": "refine", "feedback": "detalhar c1"}), cfg)
    snap = graph.get_state(cfg)
    assert snap.next == ("hitl_review",)          # pausou novamente
    assert snap.values.get("report") is None
    # feedback registrado no histórico pelo refine_analysis (mock)
    assert any(msg.get("content") == "detalhar c1" for msg in snap.values["chat_history"])

    # 2) aprova -> conclui
    final = graph.invoke(Command(resume={"action": "approve"}), cfg)
    assert graph.get_state(cfg).next == ()
    assert final["report"] is not None


def test_resume_sem_action_aprova_por_default():
    graph = build_graph()
    cfg = _cfg("hitl-default")
    graph.invoke({"diagram": _diagram(1)}, cfg)

    # dict sem "action" (não-vazio: {} dispara EmptyInputError no langgraph).
    final = graph.invoke(Command(resume={"note": "sem action"}), cfg)
    assert graph.get_state(cfg).next == ()
    assert final["report"] is not None
    assert final["hitl_approved"] is True
