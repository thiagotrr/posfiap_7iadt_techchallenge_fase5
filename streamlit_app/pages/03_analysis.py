"""streamlit_app/pages/03_analysis.py

Placeholder -- construído no Épico 3, junto com a definição do mock de
`orchestration` (Dev 3 ainda não entregou o módulo real)."""
import sys
from pathlib import Path

_STREAMLIT_APP_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _STREAMLIT_APP_DIR.parent
for _path in (_REPO_ROOT, _STREAMLIT_APP_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import streamlit as st

st.title("⚙️ Análise STRIDE")
st.info("Em construção — chega no Épico 3.")
