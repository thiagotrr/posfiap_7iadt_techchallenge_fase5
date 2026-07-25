"""tests/test_health_badge.py

Testes de streamlit_app/health_badge.py (US-2.1).
"""
from streamlit_app.health_badge import health_badge_html


def test_none_status_renders_offline_badge():
    assert health_badge_html(None) == "🔴 API indisponível"


def test_status_not_ok_renders_offline_badge():
    assert health_badge_html({"status": "degraded"}) == "🔴 API indisponível"


def test_status_ok_renders_online_badge():
    assert health_badge_html({"status": "ok", "version": "1.0.0"}) == "🟢 API conectada"
