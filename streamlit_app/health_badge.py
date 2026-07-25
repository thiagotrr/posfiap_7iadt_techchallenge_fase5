"""streamlit_app/health_badge.py

Badge de status de conexão com a API para a sidebar (US-2.1)."""
from __future__ import annotations


def health_badge_html(status: dict | None) -> str:
    """`status` é o corpo de `GET /api/v1/health` (ex. `{"status": "ok", ...}`)
    ou `None` quando `APIClient.check_health()` levantou `APIError` (API fora
    do ar)."""
    if status is None or status.get("status") != "ok":
        return "🔴 API indisponível"
    return "🟢 API conectada"
