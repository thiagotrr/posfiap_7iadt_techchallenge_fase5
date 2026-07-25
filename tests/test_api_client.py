"""tests/test_api_client.py

Testes de streamlit_app/api_client.py -- sem chamadas de rede reais, via
httpx.MockTransport (https://www.python-httpx.org/advanced/transports/#mock-transports).
"""
import json

import httpx
import pytest

from streamlit_app.api_client import APIClient, APIError

BASE_URL = "http://testserver/api/v1/"


def _client(handler) -> APIClient:
    return APIClient(base_url=BASE_URL, transport=httpx.MockTransport(handler))


def test_check_health_success():
    def handler(request):
        assert str(request.url) == "http://testserver/api/v1/health"
        return httpx.Response(200, json={"status": "ok", "version": "1.0.0"})

    client = _client(handler)
    assert client.check_health() == {"status": "ok", "version": "1.0.0"}


def test_check_health_raises_api_error_after_retries():
    def handler(request):
        return httpx.Response(503, json={"error": "Unavailable", "detail": "fora do ar"})

    client = _client(handler)
    with pytest.raises(APIError) as exc_info:
        client.check_health(retries=2)
    assert exc_info.value.status_code == 503
    assert exc_info.value.error == "Unavailable"


def test_extract_diagram_success_posts_multipart_and_returns_json():
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        captured["content_type"] = request.headers["content-type"]
        return httpx.Response(200, json={"diagram_metadata": {"cloud_provider": "AWS"}})

    client = _client(handler)
    result = client.extract_diagram(b"fake-bytes", filename="d.png", mime_type="image/png")

    assert captured["url"] == "http://testserver/api/v1/extraction/diagram"
    assert captured["content_type"].startswith("multipart/form-data")
    assert result == {"diagram_metadata": {"cloud_provider": "AWS"}}


def test_extract_diagram_502_raises_api_error_with_detail():
    def handler(request):
        return httpx.Response(
            502, json={"error": "ExtractionFailedError", "detail": "vision-detector fora do ar"}
        )

    client = _client(handler)
    with pytest.raises(APIError) as exc_info:
        client.extract_diagram(b"fake-bytes", filename="d.png", mime_type="image/png")
    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "vision-detector fora do ar"


def test_apply_patch_success_posts_diagram_and_patch_body():
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"components": []})

    client = _client(handler)
    result = client.apply_patch({"components": []}, {"patches": []})

    assert captured["url"] == "http://testserver/api/v1/extraction/diagram/patch"
    assert captured["body"] == {"diagram": {"components": []}, "patch": {"patches": []}}
    assert result == {"components": []}


def test_apply_patch_404_raises_api_error():
    def handler(request):
        return httpx.Response(
            404, json={"error": "PatchElementNotFoundError", "detail": "component 'x' não encontrado"}
        )

    client = _client(handler)
    with pytest.raises(APIError) as exc_info:
        client.apply_patch({"components": []}, {"patches": []})
    assert exc_info.value.status_code == 404


def test_apply_patch_422_raises_api_error():
    def handler(request):
        return httpx.Response(422, json={"error": "PatchValidationError", "detail": "patch inválido"})

    client = _client(handler)
    with pytest.raises(APIError):
        client.apply_patch({"components": []}, {"patches": []})


def test_check_health_200_with_invalid_json_raises_api_error():
    """Verifies that a 2xx response with malformed JSON is caught and wrapped
    in APIError instead of raising a raw JSONDecodeError/ValueError."""
    def handler(request):
        return httpx.Response(200, content=b"not json at all")

    client = _client(handler)
    with pytest.raises(APIError) as exc_info:
        client.check_health()
    assert exc_info.value.status_code == 502
    assert exc_info.value.error == "InvalidResponse"
    assert "JSON" in exc_info.value.detail
