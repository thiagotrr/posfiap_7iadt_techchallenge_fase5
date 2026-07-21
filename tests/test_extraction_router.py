"""Testes do router de extração de diagramas (vision-detector).

Mocam extraction.service.extract_diagram/apply_patch -- não precisam de
torch/ultralytics/opencv instalados nem de um serviço vision-detector no ar.
"""

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from extraction.exceptions import (
    ExtractionFailedError,
    PatchElementNotFoundError,
    PatchValidationError,
)
from extraction.fixtures import example_diagram, example_patch
from extraction.router import router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/extraction")
    return TestClient(app)


def _upload():
    return {"image": ("diagram.png", b"fake-image-bytes", "image/png")}


class TestHealth:
    def test_health_without_vision_detector_url_reports_import_mode(self, monkeypatch):
        monkeypatch.delenv("VISION_DETECTOR_URL", raising=False)

        response = _client().get("/api/v1/extraction/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "mode": "import", "vision_detector_url": None}

    def test_health_with_vision_detector_url_checks_reachability(self, monkeypatch):
        monkeypatch.setenv("VISION_DETECTOR_URL", "http://vision-detector:8000")

        with patch("extraction.router.httpx.get") as mock_get:
            mock_get.return_value.raise_for_status.return_value = None
            response = _client().get("/api/v1/extraction/health")

        assert response.status_code == 200
        assert response.json()["mode"] == "http"

    def test_health_returns_503_when_vision_detector_unreachable(self, monkeypatch):
        import httpx

        monkeypatch.setenv("VISION_DETECTOR_URL", "http://vision-detector:8000")

        with patch("extraction.router.httpx.get", side_effect=httpx.ConnectError("recusado")):
            response = _client().get("/api/v1/extraction/health")

        assert response.status_code == 503
        assert response.json()["status"] == "unavailable"


class TestCreateDiagram:
    def test_success_returns_diagram(self):
        with patch("extraction.router.extract_diagram", return_value=example_diagram):
            response = _client().post("/api/v1/extraction/diagram", files=_upload())

        assert response.status_code == 200
        assert response.json() == example_diagram.model_dump()

    def test_extraction_failure_returns_502(self):
        with patch(
            "extraction.router.extract_diagram",
            side_effect=ExtractionFailedError("vision-detector fora do ar"),
        ):
            response = _client().post("/api/v1/extraction/diagram", files=_upload())

        assert response.status_code == 502
        assert response.json()["error"] == "ExtractionFailedError"


class TestPatchDiagram:
    def _body(self, patch_dict=None):
        return {
            "diagram": example_diagram.model_dump(),
            "patch": (patch_dict or example_patch.model_dump()),
        }

    def test_success_returns_corrected_diagram(self):
        response = _client().post("/api/v1/extraction/diagram/patch", json=self._body())

        assert response.status_code == 200
        assert any(c["id"] == "comp-nat-gateway" for c in response.json()["components"])

    def test_unknown_element_id_returns_404(self):
        body = self._body({
            "patches": [{
                "op": "update", "element_type": "component",
                "element_id": "does-not-exist", "field": "name", "value": "x",
            }]
        })

        response = _client().post("/api/v1/extraction/diagram/patch", json=body)

        assert response.status_code == 404
        assert response.json()["error"] == "PatchElementNotFoundError"

    def test_invalid_result_returns_422(self):
        body = self._body({
            "patches": [{
                "op": "update", "element_type": "component",
                "element_id": "comp-cloudwatch", "field": "campo_que_nao_existe", "value": "x",
            }]
        })

        response = _client().post("/api/v1/extraction/diagram/patch", json=body)

        assert response.status_code == 422
        assert response.json()["error"] == "PatchValidationError"
