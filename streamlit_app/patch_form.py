"""streamlit_app/patch_form.py

Monta e valida um DiagramPatch a partir dos campos do formulário HITL
(US-2.3), reaproveitando os modelos Pydantic de extraction/schemas.py -- a
mesma validação que a API aplica roda aqui antes de enviar a requisição,
dando feedback imediato ao usuário.
"""
from __future__ import annotations

from typing import Any

from extraction.schemas import (
    Component,
    DataFlow,
    DiagramMetadata,
    DiagramPatch,
    ElementPatch,
    TrustBoundary,
)

_FIELD_MODELS = {
    "component": Component,
    "data_flow": DataFlow,
    "trust_boundary": TrustBoundary,
    "metadata": DiagramMetadata,
}


def editable_fields(element_type: str) -> list[str]:
    """Campos editáveis via patch 'update' para o tipo de elemento dado,
    exceto `id` (renomear o id de um elemento existente quebraria as
    referências de outros elementos a ele)."""
    model = _FIELD_MODELS[element_type]
    return [name for name in model.model_fields if name != "id"]


def validate_new_element(element_type: str, raw: dict) -> dict:
    """Valida um elemento novo (patch 'add') contra o modelo Pydantic
    correspondente antes de enviar. Levanta `pydantic.ValidationError`."""
    model = _FIELD_MODELS[element_type]
    return model.model_validate(raw).model_dump()


def build_diagram_patch(
    op: str,
    element_type: str,
    element_id: str | None,
    field: str | None,
    value: Any,
) -> dict:
    """Constrói e valida um DiagramPatch com um único ElementPatch. Levanta
    `pydantic.ValidationError` se a combinação de campos for inválida (ex.:
    'update' sem `field`) -- a página HITL captura isso e mostra `st.error()`."""
    patch = ElementPatch(op=op, element_type=element_type, element_id=element_id, field=field, value=value)
    return DiagramPatch(patches=[patch]).model_dump()
