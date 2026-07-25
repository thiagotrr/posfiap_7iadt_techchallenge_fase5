"""streamlit_app/pages/04_hitl_review.py

Tela de revisão HITL com chat de refinamento (US-3.1).

`GraphStateResponse` (contrato real da orquestração) não expõe um
`chat_history` do servidor nem a contagem de ameaças por categoria STRIDE
antes do relatório final -- só `hitl_summary` (component_id, component_name,
threats_count). Por isso o histórico de chat exibido aqui é local à sessão do
Streamlit: cada refinamento vira uma mensagem do usuário + uma mensagem de
resumo (não uma resposta textual do LLM, que a API não retorna)."""
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
st.session_state.setdefault("hitl_chat_history", [])

st.title("💬 Revisão HITL")

thread_id = st.session_state.get("thread_id")
state = st.session_state.get("analysis_state")

if not thread_id or not state:
    st.warning("Nenhuma análise em andamento. Volte para a tela de análise.")
    st.stop()

if state.get("status") == "completed":
    st.session_state["report"] = state.get("report")
    st.switch_page("pages/05_report.py")

if state.get("status") == "error":
    st.error(state.get("error_detail") or "A análise terminou em erro no servidor.")
    st.stop()

hitl_summary = state.get("hitl_summary") or []
total_threats = sum(item["threats_count"] for item in hitl_summary)

st.subheader("Resumo da análise")
st.caption(
    f"{len(hitl_summary)} componentes analisados · {total_threats} ameaças identificadas no total"
)
st.dataframe(
    [
        {"Componente": item["component_name"], "Ameaças identificadas": item["threats_count"]}
        for item in hitl_summary
    ],
    use_container_width=True,
)

refinement_turns = sum(1 for m in st.session_state["hitl_chat_history"] if m["role"] == "user")
st.caption(f"Refinamentos nesta sessão: {refinement_turns}")

st.subheader("Chat de refinamento")
for message in st.session_state["hitl_chat_history"]:
    st.chat_message(message["role"]).write(message["content"])

feedback = st.chat_input("Digite seu feedback sobre a análise...")
if feedback:
    st.session_state["hitl_chat_history"].append({"role": "user", "content": feedback})
    client = APIClient(base_url=API_BASE_URL)
    with st.spinner("Refinando análise..."):
        try:
            response = client.send_hitl_message(thread_id, "refine", feedback=feedback)
        except APIError as exc:
            st.session_state["hitl_chat_history"].append(
                {"role": "assistant", "content": f"Erro ao refinar: {exc.error}: {exc.detail}"}
            )
        else:
            st.session_state["analysis_state"] = response
            new_summary = response.get("hitl_summary") or []
            new_total = sum(item["threats_count"] for item in new_summary)
            st.session_state["hitl_chat_history"].append(
                {
                    "role": "assistant",
                    "content": f"Análise refinada. {new_total} ameaças identificadas no total.",
                }
            )
        finally:
            client.close()
    st.rerun()

st.divider()

if st.button("✅ Aprovar e Gerar Relatório", type="primary"):
    client = APIClient(base_url=API_BASE_URL)
    with st.spinner("Gerando relatório final..."):
        try:
            response = client.send_hitl_message(thread_id, "approve")
        except APIError as exc:
            st.error(f"{exc.error}: {exc.detail}")
        else:
            st.session_state["analysis_state"] = response
            if response.get("status") == "completed":
                st.session_state["report"] = response.get("report")
                st.switch_page("pages/05_report.py")
            else:
                st.warning("A aprovação não gerou o relatório esperado. Tente novamente.")
        finally:
            client.close()
