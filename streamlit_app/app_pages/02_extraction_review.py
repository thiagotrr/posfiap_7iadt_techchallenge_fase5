"""streamlit_app/app_pages/02_extraction_review.py

Tela de revisão e HITL de correção da extração (US-2.3)."""
import json
import sys
from pathlib import Path

_STREAMLIT_APP_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _STREAMLIT_APP_DIR.parent
for _path in (_REPO_ROOT, _STREAMLIT_APP_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import streamlit as st
from pydantic import ValidationError

from api_client import APIClient, APIError
from config import API_BASE_URL, init_session_state
from confidence import attention_marker, confidence_level
from patch_form import build_diagram_patch, editable_fields, validate_new_element

init_session_state(st.session_state)

diagram = st.session_state.get("diagram")

st.title("🔍 Revisão da Extração")

if not diagram:
    st.warning("Nenhum diagrama carregado. Volte para a tela de upload.")
    st.stop()

alert_functions = {"alta": st.success, "média": st.warning, "baixa": st.error}
alert_function = alert_functions.get(
    confidence_level(diagram["diagram_metadata"]["extraction_confidence"]), st.info
)
alert_function(f"Confiança da extração: {diagram['diagram_metadata']['extraction_confidence']}")

preview_image = st.session_state.get("diagram_preview_image")
if preview_image:
    st.markdown(
        """
        <style>
        [data-testid="stElementToolbar"] {
            opacity: 1 !important;
        }
        [data-testid="stElementToolbarButton"] {
            background-color: rgba(0, 0, 0, 0.6) !important;
            border-radius: 6px !important;
        }
        [data-testid="stElementToolbarButton"] svg {
            fill: white !important;
        }
        [data-testid="stElementToolbar"]:has(button[aria-label="Close fullscreen"])
            [data-testid="stElementToolbarButton"] {
            transform: scale(1.6);
            background-color: rgba(220, 38, 38, 0.9) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("🖼️ Ver detecção visual (YOLOv8)"):
        preview_col, _ = st.columns([1, 1])
        with preview_col:
            st.image(
                preview_image,
                caption="Componentes detectados pelo modelo",
                use_container_width=True,
            )
            st.download_button(
                "⬇️ Baixar imagem",
                data=preview_image,
                file_name="deteccao_yolo.png",
                mime="image/png",
            )

st.subheader("Componentes")
st.dataframe(
    [
        {
            "id": c["id"],
            "name": c["name"],
            "element_type": c["element_type"],
            "cloud_service": c.get("aws_service"),
            "trust_boundary": c["trust_boundary"],
            "Atenção": attention_marker(c.get("confidence"), c.get("note")),
        }
        for c in diagram["components"]
    ],
    use_container_width=True,
)

st.subheader("Fluxos de dados")
st.dataframe(
    [
        {
            "id": f["id"],
            "source": f["source"],
            "destination": f["destination"],
            "protocol": f["protocol"],
            "crosses_boundary": f["crosses_boundary"],
            "Atenção": attention_marker(f.get("confidence"), f.get("note")),
        }
        for f in diagram["data_flows"]
    ],
    use_container_width=True,
)

st.session_state.setdefault("patch_history", [])

with st.expander("✏️ Corrigir Campo"):
    op = st.selectbox("Operação", ["update", "remove", "add"], key="patch_op")
    element_type = st.selectbox(
        "Tipo de elemento", ["component", "data_flow", "trust_boundary", "metadata"], key="patch_element_type"
    )

    element_ids: list[str] = []
    if element_type == "component":
        element_ids = [c["id"] for c in diagram["components"]]
    elif element_type == "data_flow":
        element_ids = [f["id"] for f in diagram["data_flows"]]
    elif element_type == "trust_boundary":
        element_ids = [tb["id"] for tb in diagram["trust_boundaries"]]

    element_id = None
    if element_type != "metadata" and op in ("update", "remove"):
        element_id = st.selectbox("ID do elemento", element_ids, key="patch_element_id") if element_ids else None

    field = None
    value: object = None
    new_element_json = None

    if op == "update":
        fields = editable_fields(element_type)
        field = st.selectbox("Campo", fields, key="patch_field")
        if field == "crosses_boundary":
            value = st.toggle("Novo valor", key="patch_value_bool")
        else:
            value = st.text_input("Novo valor", key="patch_value_text")
    elif op == "add":
        new_element_json = st.text_area(
            "Novo elemento (JSON)",
            placeholder='{"id": "comp-novo", "name": "...", "element_type": "process", "trust_boundary": "tb-region"}',
            key="patch_new_element",
        )

    if st.button("Aplicar Correção"):
        try:
            if op == "add":
                if not new_element_json:
                    raise ValueError("Cole o JSON do novo elemento antes de aplicar.")
                raw = json.loads(new_element_json)
                value = validate_new_element(element_type, raw)
                patch = build_diagram_patch(op, element_type, None, None, value)
            else:
                patch = build_diagram_patch(op, element_type, element_id, field, value)

            client = APIClient(base_url=API_BASE_URL)
            try:
                updated_diagram = client.apply_patch(diagram, patch)
            finally:
                client.close()

            st.session_state["diagram"] = updated_diagram
            st.session_state["patch_history"].append(patch["patches"][0])
            st.success(f"Correção aplicada em '{element_type}'" + (f" ({element_id})" if element_id else "."))
        except json.JSONDecodeError:
            st.error("JSON inválido no campo 'Novo elemento'.")
        except (ValidationError, ValueError) as exc:
            st.error(str(exc))
        except APIError as exc:
            st.error(f"{exc.error}: {exc.detail}")

if st.session_state["patch_history"]:
    st.subheader("Histórico de correções")
    for entry in st.session_state["patch_history"]:
        st.json(entry)

is_low_confidence = confidence_level(diagram["diagram_metadata"]["extraction_confidence"]) == "baixa"
confirm_low_confidence = True
if is_low_confidence:
    confirm_low_confidence = st.checkbox(
        "Confirmo que quero prosseguir mesmo com confiança baixa na extração."
    )

if st.button(
    "Confirmar e Iniciar Análise STRIDE",
    disabled=is_low_confidence and not confirm_low_confidence,
    type="primary",
):
    st.switch_page("app_pages/03_analysis.py")
