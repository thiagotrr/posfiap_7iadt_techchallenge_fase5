"""Testes de integração do router FastAPI (US-4.1, Épico 4).

Sobe um app FastAPI com o router montado e usa TestClient. LLM mockado — nenhuma
chamada real de rede.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from orchestration.llm_client import LLMAnalysisClient
from orchestration.router import router

_VALID_JSON = json.dumps(
    [
        {
            "category": "S",
            "threat_name": "Spoofing",
            "threat_description": "desc",
            "severity": "high",
            "mitigations": ["mTLS"],
            "source": "llm_only",
        }
    ]
)

_DIAGRAM_JSON = {
    "diagram_metadata": {
        "cloud_provider": "aws",
        "region": "us-east-1",
        "extraction_confidence": "alta",
    },
    "trust_boundaries": [{"id": "tb", "name": "B", "type": "vpc", "parent": None}],
    "components": [
        {
            "id": "c1", "name": "API Gateway", "aws_service": "API Gateway",
            "element_type": "process", "category": None, "trust_boundary": "tb",
            "instance_count": 1,
        },
        {
            "id": "c2", "name": "RDS", "aws_service": "RDS",
            "element_type": "data_store", "category": None, "trust_boundary": "tb",
            "instance_count": 1,
        },
    ],
    "data_flows": [
        {
            "id": "f1", "source": "c1", "destination": "c2", "protocol": "tls",
            "crosses_boundary": True, "note": None,
        }
    ],
}


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture(autouse=True)
def _mock_llm():
    with patch.object(LLMAnalysisClient, "analyze", return_value=_VALID_JSON):
        yield


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_fluxo_completo_analyze_ate_report(client):
    # 1) inicia -> pausa no HITL
    r = client.post("/analyses", json=_DIAGRAM_JSON)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "hitl_pending"
    assert body["components_total"] == 2
    assert body["components_analyzed_count"] == 2
    assert body["report"] is None
    thread_id = body["thread_id"]

    # 2) polling do estado
    r = client.get(f"/analyses/{thread_id}")
    assert r.status_code == 200
    assert r.json()["status"] == "hitl_pending"

    # 3) relatório ainda indisponível -> 404
    assert client.get(f"/analyses/{thread_id}/report").status_code == 404

    # 4) aprova -> completa
    r = client.post(f"/analyses/{thread_id}/messages", json={"action": "approve"})
    assert r.status_code == 200
    assert r.json()["status"] == "completed"

    # 5) relatório disponível
    r = client.get(f"/analyses/{thread_id}/report")
    assert r.status_code == 200
    report = r.json()
    assert report["total_components"] == 2
    assert report["diagram_provider"] == "aws"
    assert "S" in report["stride_matrix"]


def test_refine_via_messages(client):
    thread_id = client.post("/analyses", json=_DIAGRAM_JSON).json()["thread_id"]

    r = client.post(
        f"/analyses/{thread_id}/messages",
        json={"action": "refine", "feedback": "detalhar ameaças do gateway"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "hitl_pending"  # pausou de novo

    r = client.post(f"/analyses/{thread_id}/messages", json={"action": "approve"})
    assert r.json()["status"] == "completed"


def test_refine_sem_feedback_422(client):
    thread_id = client.post("/analyses", json=_DIAGRAM_JSON).json()["thread_id"]
    r = client.post(f"/analyses/{thread_id}/messages", json={"action": "refine"})
    assert r.status_code == 422


def test_thread_desconhecida_404(client):
    assert client.get("/analyses/inexistente").status_code == 404
    assert client.get("/analyses/inexistente/report").status_code == 404
    r = client.post("/analyses/inexistente/messages", json={"action": "approve"})
    assert r.status_code == 404


def test_diagrama_invalido_422(client):
    # element_type fora do Literal do contrato de Dev 1.
    bad = json.loads(json.dumps(_DIAGRAM_JSON))
    bad["components"][0]["element_type"] = "tipo_invalido"
    r = client.post("/analyses", json=bad)
    assert r.status_code == 422
