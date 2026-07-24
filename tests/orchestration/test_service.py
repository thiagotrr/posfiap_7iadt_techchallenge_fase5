"""Testes do service.py — run_analysis / send_hitl_message / get_analysis_state
(US-3.3, Épico 3). LLM sempre mockado — nenhuma chamada real de rede.
"""
from __future__ import annotations

import json
from unittest.mock import patch

from extraction.schemas import (
    ArchitectureDiagram,
    Component,
    DataFlow,
    DiagramMetadata,
    TrustBoundary,
)
from orchestration.exceptions import GenerationError
from orchestration.llm_client import LLMAnalysisClient
from orchestration.service import (
    get_analysis_state,
    run_analysis,
    send_hitl_message,
)

_VALID_JSON = json.dumps(
    [
        {
            "category": "S",
            "threat_name": "Spoofing",
            "threat_description": "desc",
            "severity": "medium",
            "mitigations": ["m"],
            "source": "llm_only",
        }
    ]
)


def _diagram(n: int = 3) -> ArchitectureDiagram:
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


def _mock_ok():
    return patch.object(LLMAnalysisClient, "analyze", return_value=_VALID_JSON)


def test_run_analysis_pausa_no_hitl():
    with _mock_ok():
        resp = run_analysis(_diagram(3))

    assert resp.status == "hitl_pending"
    assert resp.thread_id
    assert resp.components_total == 3
    assert resp.components_analyzed_count == 3
    assert set(resp.analyzed_component_ids) == {"c1", "c2", "c3"}
    assert resp.components_failed_count == 0
    assert resp.report is None
    assert resp.hitl_summary is not None
    assert len(resp.hitl_summary) == 3


def test_get_analysis_state_reflete_pausa_sem_avancar():
    with _mock_ok():
        started = run_analysis(_diagram(2))
        state = get_analysis_state(started.thread_id)

    assert state.thread_id == started.thread_id
    assert state.status == "hitl_pending"
    assert state.components_analyzed_count == 2
    assert state.report is None


def test_send_hitl_approve_completa():
    with _mock_ok():
        started = run_analysis(_diagram(2))
        final = send_hitl_message(started.thread_id, "approve")

    assert final.status == "completed"
    assert final.report is not None
    assert final.report.total_components == 2


def test_send_hitl_refine_pausa_e_depois_aprova():
    with _mock_ok():
        started = run_analysis(_diagram(1))
        refined = send_hitl_message(started.thread_id, "refine", feedback="detalhar")
        assert refined.status == "hitl_pending"  # pausou de novo
        assert refined.report is None

        final = send_hitl_message(started.thread_id, "approve")
        assert final.status == "completed"
        assert final.report is not None


def test_components_failed_count_quando_geracao_falha():
    # Toda geração cai no fallback [] (falha de rede esgotada).
    with patch.object(LLMAnalysisClient, "analyze", side_effect=GenerationError("rede")):
        resp = run_analysis(_diagram(3))

    assert resp.status == "hitl_pending"      # grafo não aborta
    assert resp.components_analyzed_count == 3
    assert resp.components_failed_count == 3   # todos marcados como falha
    assert resp.report is None


def test_erro_de_config_nao_derruba_e_vira_status_error():
    # Exceção genérica (ex.: chave de API ausente — risco R1) não é capturada
    # pelos nós; o service converte em status="error".
    with patch.object(LLMAnalysisClient, "analyze", side_effect=RuntimeError("no api key")):
        resp = run_analysis(_diagram(2))

    assert resp.status == "error"


def test_falha_infra_kg_vira_status_error():
    # Neo4j fora do ar: retrieve_threats NÃO engole a falha de infra; ela propaga
    # e o service converte em status="error" já no 1º componente (falha rápida,
    # sem gastar tokens de LLM num relatório sem grounding).
    with _mock_ok(), patch(
        "knowledge.query.get_stride_threats",
        side_effect=RuntimeError("Neo4j ServiceUnavailable"),
    ):
        resp = run_analysis(_diagram(3))

    assert resp.status == "error"


def test_get_analysis_state_thread_desconhecida():
    resp = get_analysis_state("thread-que-nao-existe")
    assert resp.status == "error"
    assert resp.components_total == 0
