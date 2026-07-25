"""tests/test_config.py

Testes de streamlit_app/config.py (US-2.1).
"""
import importlib

from streamlit_app import config


def test_default_api_base_url_has_trailing_slash():
    assert config.API_BASE_URL.endswith("/")


def test_api_base_url_env_override(monkeypatch):
    monkeypatch.setenv("API_BASE_URL", "http://api:9000/api/v1")
    importlib.reload(config)
    try:
        assert config.API_BASE_URL == "http://api:9000/api/v1/"
    finally:
        monkeypatch.delenv("API_BASE_URL", raising=False)
        importlib.reload(config)


def test_max_upload_size_mb_env_override(monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "25")
    importlib.reload(config)
    try:
        assert config.MAX_UPLOAD_SIZE_MB == 25
    finally:
        monkeypatch.delenv("MAX_UPLOAD_SIZE_MB", raising=False)
        importlib.reload(config)


def test_init_session_state_sets_defaults_without_overwriting_existing_keys():
    state = {"diagram": {"already": "set"}}
    config.init_session_state(state)
    assert state["diagram"] == {"already": "set"}
    assert state["thread_id"] is None
    assert state["analysis_state"] is None
    assert state["report"] is None


def test_reset_downstream_state_clears_analysis_but_not_diagram():
    state = {
        "diagram": {"components": []},
        "thread_id": "thread-antigo",
        "analysis_state": {"status": "hitl_pending"},
        "report": {"total_components": 1},
        "patch_history": [{"op": "update"}],
        "hitl_chat_history": [{"role": "user", "content": "oi"}],
    }
    config.reset_downstream_state(state)

    assert state["diagram"] == {"components": []}  # não mexe no diagrama
    assert state["thread_id"] is None
    assert state["analysis_state"] is None
    assert state["report"] is None
    assert state["patch_history"] == []
    assert state["hitl_chat_history"] == []


def test_reset_downstream_state_works_on_state_without_prior_keys():
    state = {}
    config.reset_downstream_state(state)
    assert state["thread_id"] is None
    assert state["analysis_state"] is None
    assert state["report"] is None
    assert state["patch_history"] == []
    assert state["hitl_chat_history"] == []
