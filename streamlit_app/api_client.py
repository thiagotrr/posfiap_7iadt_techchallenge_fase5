"""streamlit_app/api_client.py

Cliente HTTP centralizado para as chamadas do Streamlit à API FastAPI.
"""
from __future__ import annotations

import httpx


class APIError(Exception):
    """Erro estruturado retornado pela API (`{"error": ..., "detail": ...}`)
    ou falha de rede/timeout ao tentar alcançá-la."""

    def __init__(self, status_code: int, error: str, detail: str):
        self.status_code = status_code
        self.error = error
        self.detail = detail
        super().__init__(f"[{status_code}] {error}: {detail}")


def _parse_error_response(response: httpx.Response) -> APIError:
    try:
        body = response.json()
    except ValueError:
        body = {}
    return APIError(
        status_code=response.status_code,
        error=body.get("error", "UnknownError"),
        detail=body.get("detail", response.text or "Erro sem detalhe."),
    )


class APIClient:
    """Centraliza as chamadas HTTP à API FastAPI (`/api/v1/...`).

    `base_url` deve terminar com `/` (ex.: `http://localhost:8000/api/v1/`)
    e os paths internos não devem começar com `/` -- é assim que o
    `httpx.Client(base_url=...)` combina os dois sem descartar `/api/v1`.
    """

    def __init__(self, base_url: str, transport: httpx.BaseTransport | None = None):
        self._client = httpx.Client(base_url=base_url, transport=transport)

    def close(self) -> None:
        self._client.close()

    def _request_json(self, method: str, path: str, **kwargs) -> dict:
        """Faz a requisição e devolve o JSON do corpo, ou levanta APIError -- tanto
        para erros de rede quanto para status >= 400 quanto para um corpo 2xx que
        não é JSON válido (nenhuma exceção crua deve escapar daqui)."""
        try:
            response = self._client.request(method, path, **kwargs)
        except Exception as exc:
            raise APIError(status_code=502, error="ConnectionError", detail=str(exc)) from exc

        if response.status_code >= 400:
            raise _parse_error_response(response)

        try:
            return response.json()
        except ValueError as exc:
            raise APIError(
                status_code=502,
                error="InvalidResponse",
                detail=f"Resposta não é JSON válido: {exc}",
            ) from exc

    def check_health(self, retries: int = 3, timeout: float = 5.0) -> dict:
        last_error: APIError | None = None
        for _ in range(retries):
            try:
                return self._request_json("GET", "health", timeout=timeout)
            except APIError as exc:
                last_error = exc
                continue
        assert last_error is not None
        raise last_error

    def extract_diagram(self, image_bytes: bytes, filename: str, mime_type: str) -> dict:
        return self._request_json(
            "POST",
            "extraction/diagram",
            files={"image": (filename, image_bytes, mime_type)},
            timeout=120.0,
        )

    def apply_patch(self, diagram: dict, patch: dict) -> dict:
        return self._request_json(
            "POST",
            "extraction/diagram/patch",
            json={"diagram": diagram, "patch": patch},
            timeout=30.0,
        )

    def start_analysis(self, diagram: dict) -> dict:
        # orchestration.service.run_analysis roda de forma síncrona até o
        # checkpoint HITL (várias chamadas LLM sequenciais, uma por
        # componente) -- timeout generoso, sem polling no lado do cliente.
        return self._request_json(
            "POST", "orchestration/analyses", json=diagram, timeout=600.0
        )

    def get_analysis_state(self, thread_id: str) -> dict:
        return self._request_json(
            "GET", f"orchestration/analyses/{thread_id}", timeout=30.0
        )

    def send_hitl_message(
        self, thread_id: str, action: str, feedback: str | None = None
    ) -> dict:
        payload: dict = {"action": action}
        if feedback is not None:
            payload["feedback"] = feedback
        return self._request_json(
            "POST",
            f"orchestration/analyses/{thread_id}/messages",
            json=payload,
            timeout=600.0,
        )

    def get_report(self, thread_id: str) -> dict:
        return self._request_json(
            "GET", f"orchestration/analyses/{thread_id}/report", timeout=30.0
        )
