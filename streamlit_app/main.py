"""streamlit_app/main.py

Ponto de entrada do app Streamlit (US-2.1). Roda via
`streamlit run streamlit_app/main.py` (ver Dockerfile.streamlit e
docs/development.md).
"""
import sys
from pathlib import Path

_STREAMLIT_APP_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _STREAMLIT_APP_DIR.parent
for _path in (_REPO_ROOT, _STREAMLIT_APP_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import streamlit as st

from api_client import APIClient, APIError
from config import API_BASE_URL, init_session_state
from health_badge import health_badge_html

st.set_page_config(page_title="AI Centric STRIDE Analyzer", page_icon="🛡️", layout="wide")

init_session_state(st.session_state)

PAGES = [
    st.Page(str(_STREAMLIT_APP_DIR / "pages/01_upload.py"), title="Upload do Diagrama", icon="📤", default=True),
    st.Page(str(_STREAMLIT_APP_DIR / "pages/02_extraction_review.py"), title="Revisão da Extração", icon="🔍"),
    st.Page(str(_STREAMLIT_APP_DIR / "pages/03_analysis.py"), title="Análise STRIDE", icon="⚙️"),
    st.Page(str(_STREAMLIT_APP_DIR / "pages/04_hitl_review.py"), title="Revisão HITL", icon="💬"),
    st.Page(str(_STREAMLIT_APP_DIR / "pages/05_report.py"), title="Relatório Final", icon="📊"),
]

pg = st.navigation(PAGES)

with st.sidebar:
    st.title("🛡️ STRIDE Analyzer")

    steps = " → ".join(
        f"**{i}**" if page.title == pg.title else str(i) for i, page in enumerate(PAGES, start=1)
    )
    st.caption(f"Etapa: {steps}")

    client = APIClient(base_url=API_BASE_URL)
    try:
        status = client.check_health()
    except APIError:
        status = None
    finally:
        client.close()
    st.markdown(health_badge_html(status), unsafe_allow_html=True)

pg.run()
