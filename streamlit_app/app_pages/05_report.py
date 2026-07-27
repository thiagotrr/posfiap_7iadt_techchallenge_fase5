"""streamlit_app/app_pages/05_report.py

Tela de relatório final com a matriz STRIDE (US-3.2)."""
import json
import sys
from pathlib import Path

_STREAMLIT_APP_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _STREAMLIT_APP_DIR.parent
for _path in (_REPO_ROOT, _STREAMLIT_APP_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import streamlit as st

from api_client import APIClient, APIError
from config import API_BASE_URL, init_session_state, reset_downstream_state
from stride_report import (
    category_counts,
    severity_badge_html,
    severity_counts,
    sort_component_analyses,
    stride_matrix_html,
)

init_session_state(st.session_state)

st.title("📊 Relatório Final")

report = st.session_state.get("report")
thread_id = st.session_state.get("thread_id")

if report is None and thread_id:
    client = APIClient(base_url=API_BASE_URL)
    try:
        report = client.get_report(thread_id)
        st.session_state["report"] = report
    except APIError as exc:
        st.error(f"{exc.error}: {exc.detail}")
        if st.button("Voltar para a Revisão HITL"):
            st.switch_page("app_pages/04_hitl_review.py")
        st.stop()
    finally:
        client.close()

if report is None:
    st.warning("Nenhum relatório disponível. Inicie uma nova análise.")
    st.stop()

st.subheader(f"Provedor: {report['diagram_provider'].upper()}")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Componentes", report["total_components"])
col2.metric("Ameaças identificadas", report["total_threats"])
col3.metric("Componentes com falha", report["risk_summary"].get("components_failed", 0))
col4.metric("Gerado em", report["generated_at"][:10])

st.divider()

st.subheader("Matriz STRIDE")
st.markdown(stride_matrix_html(report["component_analyses"]), unsafe_allow_html=True)

st.divider()

st.subheader("Resumo de riscos")
chart_col1, chart_col2 = st.columns(2)
with chart_col1:
    st.caption("Ameaças por severidade")
    st.bar_chart(severity_counts(report["risk_summary"]), horizontal=True)
with chart_col2:
    st.caption("Ameaças por categoria STRIDE")
    st.bar_chart(category_counts(report["risk_summary"]), horizontal=True)

st.divider()

st.subheader("Detalhamento por componente")
for analysis in sort_component_analyses(report["component_analyses"]):
    threats_count = len(analysis["stride_entries"])
    with st.expander(f"{analysis['component_name']} ({threats_count} ameaças)"):
        st.caption(
            f"Tipo: {analysis['element_type']} · "
            f"Serviço: {analysis.get('cloud_service') or '—'} · "
            f"Trust boundary: {analysis['trust_boundary']}"
        )
        if not analysis["stride_entries"]:
            st.info("Nenhuma ameaça identificada para este componente.")
        for entry in analysis["stride_entries"]:
            st.markdown(
                f"**{entry['category']} — {entry['threat_name']}** &nbsp; {severity_badge_html(entry['severity'])}",
                unsafe_allow_html=True,
            )
            st.markdown(entry["threat_description"])
            st.markdown("Mitigações: " + "; ".join(entry["mitigations"]))
            st.markdown("---")

st.divider()

button_col1, button_col2 = st.columns(2)
with button_col1:
    st.download_button(
        "📥 Exportar JSON",
        data=json.dumps(report, ensure_ascii=False, indent=2),
        file_name=f"stride_report_{thread_id or 'analise'}.json",
        mime="application/json",
    )
with button_col2:
    if st.button("🔄 Nova Análise"):
        reset_downstream_state(st.session_state)
        st.session_state["diagram"] = None
        st.switch_page("app_pages/01_upload.py")
