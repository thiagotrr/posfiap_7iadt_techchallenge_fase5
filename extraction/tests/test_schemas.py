import pytest
from pydantic import ValidationError

from extraction.fixtures import example_diagram
from extraction.schemas import ArchitectureDiagram, DiagramPatch, ElementPatch


def _diagram_dict():
    return example_diagram.model_dump()


class TestReferentialIntegrity:
    def test_valid_diagram_passes(self):
        ArchitectureDiagram.model_validate(_diagram_dict())

    def test_component_with_unknown_trust_boundary_fails(self):
        data = _diagram_dict()
        data["components"][0]["trust_boundary"] = "does-not-exist"
        with pytest.raises(ValidationError, match="trust_boundary"):
            ArchitectureDiagram.model_validate(data)

    def test_boundary_with_unknown_parent_fails(self):
        data = _diagram_dict()
        data["trust_boundaries"][0]["parent"] = "does-not-exist"
        with pytest.raises(ValidationError, match="parent"):
            ArchitectureDiagram.model_validate(data)

    def test_flow_with_unknown_source_fails(self):
        data = _diagram_dict()
        data["data_flows"][0]["source"] = "does-not-exist"
        with pytest.raises(ValidationError, match="source"):
            ArchitectureDiagram.model_validate(data)

    def test_flow_with_unknown_destination_fails(self):
        data = _diagram_dict()
        data["data_flows"][0]["destination"] = "does-not-exist"
        with pytest.raises(ValidationError, match="destination"):
            ArchitectureDiagram.model_validate(data)


class TestStrictFields:
    def test_unknown_field_on_component_is_rejected(self):
        data = _diagram_dict()
        data["components"][0]["totally_bogus_field"] = "x"
        with pytest.raises(ValidationError):
            ArchitectureDiagram.model_validate(data)

    def test_confidence_and_note_are_optional(self):
        data = _diagram_dict()
        data["components"][0]["confidence"] = 0.83
        data["components"][0]["note"] = "revisar"
        diagram = ArchitectureDiagram.model_validate(data)
        assert diagram.components[0].confidence == 0.83
        assert diagram.components[0].note == "revisar"


class TestElementPatch:
    def test_valid_update(self):
        ElementPatch.model_validate({
            "op": "update", "element_type": "component",
            "element_id": "c1", "field": "name", "value": "novo nome",
        })

    def test_update_without_element_id_fails(self):
        with pytest.raises(ValidationError):
            ElementPatch.model_validate({
                "op": "update", "element_type": "component", "field": "name", "value": "x",
            })

    def test_update_without_field_fails(self):
        with pytest.raises(ValidationError):
            ElementPatch.model_validate({
                "op": "update", "element_type": "component", "element_id": "c1", "value": "x",
            })

    def test_remove_without_element_id_fails(self):
        with pytest.raises(ValidationError):
            ElementPatch.model_validate({"op": "remove", "element_type": "component"})

    def test_valid_remove(self):
        ElementPatch.model_validate({"op": "remove", "element_type": "component", "element_id": "c1"})

    def test_add_requires_dict_value(self):
        with pytest.raises(ValidationError):
            ElementPatch.model_validate({"op": "add", "element_type": "component", "value": "not-a-dict"})

    def test_add_requires_id_in_value(self):
        with pytest.raises(ValidationError):
            ElementPatch.model_validate({
                "op": "add", "element_type": "component", "value": {"name": "sem id"},
            })

    def test_valid_add(self):
        ElementPatch.model_validate({
            "op": "add", "element_type": "component",
            "value": {"id": "c99", "name": "x", "element_type": "process", "trust_boundary": "tb1"},
        })

    def test_metadata_only_supports_update(self):
        with pytest.raises(ValidationError):
            ElementPatch.model_validate({"op": "remove", "element_type": "metadata", "element_id": "irrelevante"})

    def test_metadata_update_does_not_need_element_id(self):
        ElementPatch.model_validate({
            "op": "update", "element_type": "metadata", "field": "region", "value": "us-east-1",
        })


def test_diagram_patch_accepts_list_of_patches():
    patch = DiagramPatch.model_validate({
        "patches": [
            {"op": "update", "element_type": "component", "element_id": "c1", "field": "name", "value": "x"},
            {"op": "remove", "element_type": "data_flow", "element_id": "f1"},
        ]
    })
    assert len(patch.patches) == 2
