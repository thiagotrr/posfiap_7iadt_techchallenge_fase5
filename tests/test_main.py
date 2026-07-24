"""
tests/test_main.py

Testes do skeleton FastAPI (US-1.1).
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check_returns_200_and_expected_body():
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == "1.0.0"


def test_unknown_route_returns_404_with_structured_json():
    response = client.get("/api/v1/nao-existe")

    assert response.status_code == 404
    body = response.json()
    assert "error" in body
    assert "detail" in body


def test_cors_allows_configured_streamlit_origin():
    response = client.get(
        "/api/v1/health",
        headers={"Origin": "http://localhost:8501"},
    )

    assert response.headers["access-control-allow-origin"] == "http://localhost:8501"


def test_extraction_unknown_route_returns_404():
    # extraction deixou de ser stub (ver extraction/router.py) -- rota
    # desconhecida agora se comporta como qualquer outro router real.
    response = client.get("/api/v1/extraction/nao-existe")

    assert response.status_code == 404


def test_knowledge_unknown_route_returns_404():
    response = client.get("/api/v1/knowledge/nao-existe")

    assert response.status_code == 404


def test_orchestration_router_montado():
    # Integração Dev 3: o router real substituiu o stub 503.
    health = client.get("/api/v1/orchestration/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"


def test_orchestration_unknown_route_returns_404():
    response = client.get("/api/v1/orchestration/nao-existe")

    assert response.status_code == 404
