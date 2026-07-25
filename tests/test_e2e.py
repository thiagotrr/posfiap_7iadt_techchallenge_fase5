"""tests/test_e2e.py

Testes de integração E2E (US-4.2): fluxo completo através do app FastAPI real
(app.main:app, com CORS/lifespan/handlers montados) cobrindo os três módulos
juntos -- extração (Dev 1) -> patch HITL -> orquestração STRIDE (Dev 3, com
KG do Dev 2). Nenhuma chamada de rede real: LLM da orquestração e
vision-detector da extração são mockados; a consulta ao Knowledge Graph cai
no fallback determinístico de fixtures (mesmo padrão de
tests/orchestration/conftest.py, que não se aplica aqui por estar fora dessa
árvore de diretórios) -- não depende de Neo4j de pé.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from extraction.exceptions import ExtractionFailedError
from extraction.fixtures import example_diagram
from knowledge.fixtures import get_fixture_for
from orchestration.llm_client import LLMAnalysisClient

_VALID_LLM_JSON = json.dumps(
    [
        {
            "category": "S",
            "threat_name": "Falsificação de identidade",
            "threat_description": "Ator não autenticado tenta se passar por cliente legítimo.",
            "severity": "high",
            "mitigations": ["Autenticação forte"],
            "source": "llm_only",
        }
    ]
)


@pytest.fixture(autouse=True)
def _mock_kg_query():
    """Mesma estratégia de tests/orchestration/conftest.py::_mock_kg_query --
    não depende de Neo4j de pé, delega ao fixture determinístico do Dev 2."""

    def _fake(element_type, cloud_service=None, driver=None):
        return get_fixture_for(element_type)

    with patch("knowledge.query.get_stride_threats", side_effect=_fake):
        yield


@pytest.fixture(autouse=True)
def _mock_llm():
    with patch.object(LLMAnalysisClient, "analyze", return_value=_VALID_LLM_JSON):
        yield


@pytest.fixture
def client():
    return TestClient(app)


def test_e2e_fluxo_feliz_upload_ate_relatorio(client):
    diagram = example_diagram.model_dump()

    # 1) extração (mock do vision-detector) -- endpoint real é /extraction/diagram.
    with patch("extraction.router.extract_diagram", return_value=example_diagram):
        r = client.post(
            "/api/v1/extraction/diagram",
            files={"image": ("diagrama.png", b"fake-bytes", "image/png")},
        )
    assert r.status_code == 200
    extracted = r.json()
    assert len(extracted["components"]) == 14

    # 2) patch HITL de correção -- corrige o nome do primeiro componente.
    first_id = extracted["components"][0]["id"]
    patch_body = {
        "diagram": extracted,
        "patch": {
            "patches": [
                {
                    "op": "update",
                    "element_type": "component",
                    "element_id": first_id,
                    "field": "name",
                    "value": "Nome corrigido via HITL",
                }
            ]
        },
    }
    r = client.post("/api/v1/extraction/diagram/patch", json=patch_body)
    assert r.status_code == 200
    corrected = r.json()
    assert corrected["components"][0]["name"] == "Nome corrigido via HITL"

    # 3) inicia a análise STRIDE -- roda síncrono até o checkpoint HITL.
    r = client.post("/api/v1/orchestration/analyses", json=corrected)
    assert r.status_code == 200
    state = r.json()
    assert state["status"] == "hitl_pending"
    assert state["components_total"] == 14
    assert state["components_analyzed_count"] == 14
    thread_id = state["thread_id"]

    # 4) polling do estado (GET) -- reflete o mesmo status sem avançar o grafo.
    r = client.get(f"/api/v1/orchestration/analyses/{thread_id}")
    assert r.status_code == 200
    assert r.json()["status"] == "hitl_pending"

    # 5) relatório ainda indisponível antes da aprovação.
    assert client.get(f"/api/v1/orchestration/analyses/{thread_id}/report").status_code == 404

    # 6) aprova -> gera o relatório final.
    r = client.post(f"/api/v1/orchestration/analyses/{thread_id}/messages", json={"action": "approve"})
    assert r.status_code == 200
    assert r.json()["status"] == "completed"

    # 7) relatório final com os 14 componentes.
    r = client.get(f"/api/v1/orchestration/analyses/{thread_id}/report")
    assert r.status_code == 200
    report = r.json()
    assert report["total_components"] == 14
    assert report["diagram_provider"] == extracted["diagram_metadata"]["cloud_provider"]
    assert "S" in report["stride_matrix"]


def test_e2e_fluxo_refinamento_hitl(client):
    diagram = example_diagram.model_dump()
    thread_id = client.post("/api/v1/orchestration/analyses", json=diagram).json()["thread_id"]

    r = client.post(
        f"/api/v1/orchestration/analyses/{thread_id}/messages",
        json={"action": "refine", "feedback": "detalhar ameaças do componente de borda"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "hitl_pending"  # pausou de novo após o refinamento

    r = client.post(f"/api/v1/orchestration/analyses/{thread_id}/messages", json={"action": "approve"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert body["report"]["total_components"] == 14


def test_e2e_recuperacao_de_sessao_via_novo_test_client(client):
    diagram = example_diagram.model_dump()
    thread_id = client.post("/api/v1/orchestration/analyses", json=diagram).json()["thread_id"]

    # Um novo TestClient simula uma nova requisição HTTP -- o estado do
    # LangGraph (MemorySaver) vive no processo do app, não na conexão, então
    # o thread_id continua recuperável por qualquer client novo.
    outro_client = TestClient(app)
    r = outro_client.get(f"/api/v1/orchestration/analyses/{thread_id}")
    assert r.status_code == 200
    assert r.json()["status"] == "hitl_pending"


def test_e2e_falha_de_extracao_retorna_erro_semantico(client):
    with patch(
        "extraction.router.extract_diagram",
        side_effect=ExtractionFailedError("JSON inválido retornado pelo vision-detector"),
    ):
        r = client.post(
            "/api/v1/extraction/diagram",
            files={"image": ("diagrama.png", b"fake-bytes", "image/png")},
        )

    assert r.status_code == 502
    body = r.json()
    assert body["error"] == "ExtractionFailedError"
    assert "JSON inválido" in body["detail"]


def test_e2e_thread_id_inexistente_404(client):
    assert client.get("/api/v1/orchestration/analyses/nao-existe").status_code == 404
    assert client.get("/api/v1/orchestration/analyses/nao-existe/report").status_code == 404
    r = client.post("/api/v1/orchestration/analyses/nao-existe/messages", json={"action": "approve"})
    assert r.status_code == 404
