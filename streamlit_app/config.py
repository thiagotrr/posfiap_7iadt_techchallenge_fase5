"""streamlit_app/config.py

Configuração do app Streamlit lida via variáveis de ambiente. Não importa
`api_client` nem qualquer outro módulo de streamlit_app -- mantém-se sem
dependências cruzadas, o que evita ciclos de import e facilita testar.
"""
import os


def _resolve_api_base_url() -> str:
    raw = os.environ.get("API_BASE_URL", "http://localhost:8000/api/v1")
    return raw.rstrip("/") + "/"


API_BASE_URL = _resolve_api_base_url()
MAX_UPLOAD_SIZE_MB = int(os.environ.get("MAX_UPLOAD_SIZE_MB", "10"))
ALLOWED_UPLOAD_TYPES = ["png", "jpg", "jpeg", "webp"]

DEFAULT_SESSION_STATE = {
    "diagram": None,
    "thread_id": None,
    "analysis_state": None,
    "report": None,
}


def init_session_state(session_state) -> None:
    """Preenche `session_state` com os valores default, sem sobrescrever
    chaves já definidas (idempotente entre reruns do Streamlit)."""
    for key, value in DEFAULT_SESSION_STATE.items():
        if key not in session_state:
            session_state[key] = value


def reset_downstream_state(session_state) -> None:
    """Limpa thread_id/analysis_state/report e os históricos locais de uma
    análise anterior. Chamado sempre que um NOVO diagrama é carregado (upload
    real ou "Usar Diagrama de Exemplo") -- sem isso, `pages/03_analysis.py`
    encontra um `thread_id` de uma análise antiga ainda em session_state e
    pula direto pro resultado velho (hitl_pending/completed) em vez de
    iniciar uma análise nova para o diagrama recém-carregado."""
    session_state["thread_id"] = None
    session_state["analysis_state"] = None
    session_state["report"] = None
    session_state["patch_history"] = []
    session_state["hitl_chat_history"] = []
