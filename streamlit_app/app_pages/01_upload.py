"""streamlit_app/app_pages/01_upload.py

Tela de upload do diagrama (US-2.2)."""
import sys
from pathlib import Path

_STREAMLIT_APP_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _STREAMLIT_APP_DIR.parent
for _path in (_REPO_ROOT, _STREAMLIT_APP_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import streamlit as st

from api_client import APIClient, APIError
from config import (
    ALLOWED_UPLOAD_TYPES,
    API_BASE_URL,
    MAX_UPLOAD_SIZE_MB,
    init_session_state,
    reset_downstream_state,
)
from validation import validate_upload

init_session_state(st.session_state)

# Streamlit não tem opção nativa de traduzir o texto interno do
# file_uploader ("Drag and drop file here", "Limit XXMB per file...",
# "Browse files") -- não existe parâmetro de i18n na API do widget. O truque
# abaixo esconde o texto original (via `visibility`/`font-size`, não
# `display: none`, pra não quebrar o layout) e sobrepõe a tradução via
# `::after`, usando os `data-testid` do Streamlit como seletor (mais estável
# entre versões do que as classes `st-emotion-cache-*`, que são geradas e
# mudam a cada build). Se o time atualizar o Streamlit e o `data-testid`
# mudar, ou se o limite de upload do servidor mudar de 200MB, os seletores
# e o texto do limite abaixo precisam ser conferidos de novo.
st.markdown(
    """
    <style>
    [data-testid="stFileUploaderDropzoneInstructions"] > div > span {
        visibility: hidden;
        position: relative;
    }
    [data-testid="stFileUploaderDropzoneInstructions"] > div > span::after {
        content: "Arraste e solte o arquivo aqui";
        visibility: visible;
        position: absolute;
        top: 0;
        left: 0;
    }
    [data-testid="stFileUploaderDropzoneInstructions"] > div > small {
        visibility: hidden;
        position: relative;
    }
    [data-testid="stFileUploaderDropzoneInstructions"] > div > small::after {
        content: "Limite de 200MB por arquivo • PNG, JPG, JPEG, WEBP";
        visibility: visible;
        position: absolute;
        top: 0;
        left: 0;
    }
    [data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"] {
        font-size: 0;
    }
    [data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"]::after {
        content: "Procurar arquivos";
        font-size: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📤 Upload do Diagrama")

uploaded_file = st.file_uploader("Diagrama de arquitetura", type=ALLOWED_UPLOAD_TYPES)

if uploaded_file is not None:
    st.image(uploaded_file)

    error = validate_upload(
        size_bytes=uploaded_file.size,
        mime_type=uploaded_file.type,
        max_size_mb=MAX_UPLOAD_SIZE_MB,
        allowed_types=ALLOWED_UPLOAD_TYPES,
    )

    if error:
        st.error(error)
    elif st.button("Extrair Diagrama", type="primary"):
        client = APIClient(base_url=API_BASE_URL)
        with st.spinner("Extraindo componentes via visão computacional (YOLOv8)..."):
            try:
                diagram = client.extract_diagram(
                    image_bytes=uploaded_file.getvalue(),
                    filename=uploaded_file.name,
                    mime_type=uploaded_file.type,
                )
            except APIError as exc:
                st.error(f"{exc.error}: {exc.detail}")
            else:
                reset_downstream_state(st.session_state)
                st.session_state["diagram"] = diagram
                try:
                    st.session_state["diagram_preview_image"] = client.get_extraction_preview(
                        image_bytes=uploaded_file.getvalue(),
                        filename=uploaded_file.name,
                        mime_type=uploaded_file.type,
                    )
                except APIError:
                    st.session_state["diagram_preview_image"] = None
                st.switch_page("app_pages/02_extraction_review.py")
            finally:
                client.close()

st.divider()

if st.button("Usar Diagrama de Exemplo"):
    from extraction.fixtures import example_diagram

    reset_downstream_state(st.session_state)
    st.session_state["diagram"] = example_diagram.model_dump()
    st.session_state["diagram_preview_image"] = None  # exemplo não tem imagem-fonte pra anotar
    st.switch_page("app_pages/02_extraction_review.py")
