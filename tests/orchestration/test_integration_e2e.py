"""Teste de integração end-to-end (US-4.3, Épico 4).

Percorre toda a pilha (router HTTP → service → grafo → HITL → relatório) sobre um
diagrama de 14 componentes com tipos mistos, incluindo o ciclo refine→approve.
LLM mockado — nenhuma chamada real de rede.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from orchestration.llm_client import LLMAnalysisClient
from orchestration.router import router

# Mock retorna 2 ameaças fora de ordem de severidade (D/low antes de S/critical),
# para exercitar a ordenação do relatório.
_MOCK_JSON = json.dumps(
    [
        {"category": "D", "threat_name": "DoS", "threat_description": "d",
         "severity": "low", "mitigations": ["m"], "source": "llm_only"},
        {"category": "S", "threat_name": "Spoof", "threat_description": "d",
         "severity": "critical", "mitigations": ["m"], "source": "llm_only"},
    ]
)

_ELEMENT_TYPES = ["process", "data_store", "data_flow", "external_entity"]


def _diagram_14() -> dict:
    components = []
    for i in range(1, 15):
        components.append(
            {
                "id": f"c{i}",
                "name": f"Componente {i}",
                "aws_service": "AWS Service",
                "element_type": _ELEMENT_TYPES[i % len(_ELEMENT_TYPES)],
                "category": None,
                "trust_boundary": "tb-main",
                "instance_count": 1,
            }
        )
    return {
        "diagram_metadata": {
            "cloud_provider": "aws", "region": "us-east-1",
            "extraction_confidence": "alta",
        },
        "trust_boundaries": [
            {"id": "tb-main", "name": "Main", "type": "vpc", "parent": None}
        ],
        "components": components,
        "data_flows": [
            {"id": "f1", "source": "c1", "destination": "c2", "protocol": "tls",
             "crosses_boundary": True, "note": None}
        ],
    }


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture(autouse=True)
def _mock_llm():
    with patch.object(LLMAnalysisClient, "analyze", return_value=_MOCK_JSON):
        yield


def test_e2e_14_componentes_refine_e_approve(client):
    # 1) inicia — 14 componentes analisados, pausa no HITL
    r = client.post("/analyses", json=_diagram_14())
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "hitl_pending"
    assert body["components_total"] == 14
    assert body["components_analyzed_count"] == 14
    assert body["components_failed_count"] == 0
    assert len(body["hitl_summary"]) == 14
    thread_id = body["thread_id"]

    # 2) refina — volta a pausar
    r = client.post(
        f"/analyses/{thread_id}/messages",
        json={"action": "refine", "feedback": "priorizar ameaças críticas"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "hitl_pending"

    # 3) aprova — conclui
    r = client.post(f"/analyses/{thread_id}/messages", json={"action": "approve"})
    assert r.json()["status"] == "completed"

    # 4) relatório final enriquecido
    report = client.get(f"/analyses/{thread_id}/report").json()
    assert report["total_components"] == 14
    assert report["total_threats"] == 28  # 2 por componente

    rs = report["risk_summary"]
    assert rs["critical"] == 14 and rs["low"] == 14
    assert rs["by_category"]["S"] == 14 and rs["by_category"]["D"] == 14
    assert rs["components_with_threats"] == 14
    assert rs["components_without_threats"] == 0
    assert rs["components_failed"] == 0

    # matriz cobre todos os componentes em S e D
    assert len(report["stride_matrix"]["S"]) == 14
    assert len(report["stride_matrix"]["D"]) == 14

    # ordenação: em cada componente, crítico antes de low
    for analysis in report["component_analyses"]:
        severities = [e["severity"] for e in analysis["stride_entries"]]
        assert severities == ["critical", "low"]
