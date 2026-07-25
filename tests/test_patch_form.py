"""tests/test_patch_form.py

Testes de streamlit_app/patch_form.py (US-2.3).
"""
import pytest
from pydantic import ValidationError

from streamlit_app.patch_form import (
    build_diagram_patch,
    editable_fields,
    validate_new_element,
)


def test_editable_fields_for_component_excludes_id():
    fields = editable_fields("component")
    assert "id" not in fields
    assert "name" in fields
    assert "trust_boundary" in fields


def test_editable_fields_for_data_flow_includes_crosses_boundary():
    fields = editable_fields("data_flow")
    assert "crosses_boundary" in fields
    assert "id" not in fields


def test_editable_fields_for_trust_boundary_excludes_id():
    fields = editable_fields("trust_boundary")
    assert "id" not in fields
    assert "parent" in fields


def test_editable_fields_for_metadata_lists_diagram_metadata_fields():
    fields = editable_fields("metadata")
    assert set(fields) == {"cloud_provider", "region", "extraction_confidence"}


def test_validate_new_element_component_success():
    element = validate_new_element(
        "component",
        {
            "id": "comp-new",
            "name": "Novo Componente",
            "aws_service": None,
            "element_type": "process",
            "trust_boundary": "tb-region",
        },
    )
    assert element["id"] == "comp-new"


def test_validate_new_element_missing_required_field_raises():
    with pytest.raises(ValidationError):
        validate_new_element("component", {"id": "comp-new", "name": "Sem trust boundary"})


def test_build_diagram_patch_update_returns_valid_patch_dict():
    patch = build_diagram_patch("update", "component", "comp-1", "name", "Novo nome")
    assert patch == {
        "patches": [
            {
                "op": "update",
                "element_type": "component",
                "element_id": "comp-1",
                "field": "name",
                "value": "Novo nome",
            }
        ]
    }


def test_build_diagram_patch_update_without_field_raises_validation_error():
    with pytest.raises(ValidationError):
        build_diagram_patch("update", "component", "comp-1", None, "valor")


def test_build_diagram_patch_remove_is_valid():
    patch = build_diagram_patch("remove", "trust_boundary", "tb-x", None, None)
    assert patch["patches"][0]["op"] == "remove"
