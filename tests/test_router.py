"""Testes do router de health-check do Knowledge Graph."""

from contextlib import nullcontext
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from knowledge.router import router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/knowledge")
    return TestClient(app)


def test_health_returns_populated_counts():
    session = MagicMock()
    results = []
    for count in (4, 6, 12, 12):
        result = MagicMock()
        result.single.return_value = {"cnt": count}
        results.append(result)
    session.run.side_effect = results

    with patch(
        "knowledge.router.get_session",
        return_value=nullcontext(session),
    ):
        response = _client().get("/api/v1/knowledge/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "kg_populated": True,
        "node_counts": {
            "element_types": 4,
            "stride_categories": 6,
            "threats": 12,
            "mitigations": 12,
        },
    }


def test_health_returns_503_without_exposing_connection_details():
    with patch(
        "knowledge.router.get_session",
        side_effect=RuntimeError("bolt://private-host:7687 password=secret"),
    ):
        response = _client().get("/api/v1/knowledge/health")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "unavailable"
    assert "secret" not in response.text
    assert "traceback" not in response.text.lower()
