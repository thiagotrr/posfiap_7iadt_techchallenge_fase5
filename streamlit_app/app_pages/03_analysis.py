"""streamlit_app/app_pages/03_analysis.py

Tela de disparo e acompanhamento da análise STRIDE (US-2.4 / Épico 3).

`orchestration.service.run_analysis` roda de forma síncrona até o checkpoint
HITL (ver orchestration/README.md) -- por isso não há polling em loop aqui: a
chamada à API já bloqueia (com spinner) até a resposta trazer o status final
daquela etapa (`hitl_pending`, `completed` ou `error`)."""
import sys
from pathlib import Path

_STREAMLIT_APP_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _STREAMLIT_APP_DIR.parent
for _path in (_REPO_ROOT, _STREAMLIT_APP_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import streamlit as st

from api_client import APIClient, APIError
from config import API_BASE_URL, init_session_state

init_session_state(st.session_state)

diagram = st.session_state.get("diagram")

st.title("⚙️ Análise STRIDE")

if not diagram:
    st.warning("Nenhum diagrama carregado. Volte para a tela de upload.")
    st.stop()

if st.session_state["thread_id"] is None:
    client = APIClient(base_url=API_BASE_URL)
    with st.spinner("Executando análise STRIDE via LLM — isso pode levar alguns minutos..."):
        try:
            response = client.start_analysis(diagram)
        except APIError as exc:
            st.session_state["analysis_state"] = {
                "status": "error",
                "error_detail": f"{exc.error}: {exc.detail}",
            }
        else:
            st.session_state["thread_id"] = response["thread_id"]
            st.session_state["analysis_state"] = response
        finally:
            client.close()

state = st.session_state["analysis_state"] or {}
status = state.get("status")

if status == "hitl_pending":
    st.info("Análise concluída. Redirecionando para a revisão HITL...")
    st.switch_page("app_pages/04_hitl_review.py")
elif status == "completed":
    st.session_state["report"] = state.get("report")
    st.switch_page("app_pages/05_report.py")
elif status == "error":
    st.error(state.get("error_detail") or "A análise terminou em erro no servidor.")
    if st.button("Tentar novamente", type="primary"):
        st.session_state["thread_id"] = None
        st.session_state["analysis_state"] = None
else:
    st.info(
        f"Progresso: {state.get('components_analyzed_count', 0)}/"
        f"{state.get('components_total', 0)} componentes analisados."
    )
    if state.get("analyzed_component_ids"):
        st.caption("Componentes já analisados: " + ", ".join(state["analyzed_component_ids"]))
    if st.button("Atualizar status"):
        client = APIClient(base_url=API_BASE_URL)
        try:
            st.session_state["analysis_state"] = client.get_analysis_state(state["thread_id"])
        except APIError as exc:
            st.error(f"{exc.error}: {exc.detail}")
        finally:
            client.close()
