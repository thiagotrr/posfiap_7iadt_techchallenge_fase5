import sys
import types

import pytest

from extraction.exceptions import ExtractionFailedError, PatchElementNotFoundError, PatchValidationError
from extraction.fixtures import example_diagram, example_patch
from extraction.schemas import DiagramPatch
from extraction.service import apply_patch, extract_diagram


@pytest.fixture
def fake_predict_module(monkeypatch):
    """Substitui o módulo `predict` (vision-detector) por um fake em
    sys.modules -- evita depender de torch/ultralytics/cv2 só pra testar a
    orquestração em extraction/service.py. Também garante VISION_DETECTOR_URL
    ausente, senão extract_diagram cairia no modo HTTP em vez de import."""
    monkeypatch.delenv("VISION_DETECTOR_URL", raising=False)
    module = types.ModuleType("predict")
    module.detect_architecture = lambda image_path: example_diagram
    monkeypatch.setitem(sys.modules, "predict", module)
    return module


class TestExtractDiagramImportMode:
    """Modo usado quando VISION_DETECTOR_URL não está definida (sem Docker)."""

    def test_success_returns_diagram(self, fake_predict_module):
        result = extract_diagram(b"fake-image-bytes", mime_type="image/png")
        assert result == example_diagram

    def test_failure_wraps_as_extraction_failed_error(self, monkeypatch):
        monkeypatch.delenv("VISION_DETECTOR_URL", raising=False)
        module = types.ModuleType("predict")

        def _boom(image_path):
            raise RuntimeError("modelo não carregou")

        module.detect_architecture = _boom
        monkeypatch.setitem(sys.modules, "predict", module)

        with pytest.raises(ExtractionFailedError):
            extract_diagram(b"fake-image-bytes")


class TestExtractDiagramHttpMode:
    """Modo usado quando VISION_DETECTOR_URL está definida (Docker,
    serviço vision-detector separado -- ver models/vision-detector/api.py)."""

    def test_success_returns_diagram(self, monkeypatch):
        import httpx

        monkeypatch.setenv("VISION_DETECTOR_URL", "http://vision-detector:8000")

        class _FakeResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return example_diagram.model_dump()

        def _fake_post(url, **kwargs):
            assert url == "http://vision-detector:8000/predict"
            return _FakeResponse()

        monkeypatch.setattr(httpx, "post", _fake_post)

        result = extract_diagram(b"fake-image-bytes", mime_type="image/png")
        assert result == example_diagram

    def test_unreachable_service_wraps_as_extraction_failed_error(self, monkeypatch):
        import httpx

        monkeypatch.setenv("VISION_DETECTOR_URL", "http://vision-detector:8000")

        def _fake_post(url, **kwargs):
            raise httpx.ConnectError("recusado")

        monkeypatch.setattr(httpx, "post", _fake_post)

        with pytest.raises(ExtractionFailedError):
            extract_diagram(b"fake-image-bytes")


class TestApplyPatch:
    def test_update_changes_field_without_mutating_original(self):
        patch = DiagramPatch.model_validate({
            "patches": [{
                "op": "update", "element_type": "component",
                "element_id": "comp-cloudwatch", "field": "name", "value": "Novo Nome",
            }]
        })
        result = apply_patch(example_diagram, patch)

        assert next(c.name for c in result.components if c.id == "comp-cloudwatch") == "Novo Nome"
        original_name = next(c.name for c in example_diagram.components if c.id == "comp-cloudwatch")
        assert original_name != "Novo Nome"  # original não mutado

    def test_add_appends_new_component(self):
        patch = DiagramPatch.model_validate({
            "patches": [{
                "op": "add", "element_type": "component",
                "value": {
                    "id": "comp-new", "name": "Novo", "element_type": "process",
                    "trust_boundary": "tb-region",
                },
            }]
        })
        result = apply_patch(example_diagram, patch)

        assert len(result.components) == len(example_diagram.components) + 1
        assert any(c.id == "comp-new" for c in result.components)

    def test_remove_deletes_element(self):
        patch = DiagramPatch.model_validate({
            "patches": [{"op": "remove", "element_type": "data_flow", "element_id": "df-11"}]
        })
        result = apply_patch(example_diagram, patch)

        assert not any(f.id == "df-11" for f in result.data_flows)
        assert len(result.data_flows) == len(example_diagram.data_flows) - 1

    def test_update_unknown_element_id_raises_not_found(self):
        patch = DiagramPatch.model_validate({
            "patches": [{
                "op": "update", "element_type": "component",
                "element_id": "does-not-exist", "field": "name", "value": "x",
            }]
        })
        with pytest.raises(PatchElementNotFoundError):
            apply_patch(example_diagram, patch)

    def test_remove_breaking_referential_integrity_raises_validation_error(self):
        # tb-az1 ainda é referenciada por vários componentes -- removê-la sem
        # reatribuí-los antes deve falhar na revalidação final do patch.
        patch = DiagramPatch.model_validate({
            "patches": [{"op": "remove", "element_type": "trust_boundary", "element_id": "tb-az1"}]
        })
        with pytest.raises(PatchValidationError):
            apply_patch(example_diagram, patch)

    def test_update_unknown_field_raises_validation_error(self):
        # extra="forbid" nos modelos de elemento é o que faz isso estourar
        # alto em vez de silenciosamente não fazer nada.
        patch = DiagramPatch.model_validate({
            "patches": [{
                "op": "update", "element_type": "component",
                "element_id": "comp-cloudwatch", "field": "campo_que_nao_existe", "value": "x",
            }]
        })
        with pytest.raises(PatchValidationError):
            apply_patch(example_diagram, patch)

    def test_metadata_update(self):
        patch = DiagramPatch.model_validate({
            "patches": [{"op": "update", "element_type": "metadata", "field": "region", "value": "sa-east-1"}]
        })
        result = apply_patch(example_diagram, patch)
        assert result.diagram_metadata.region == "sa-east-1"

    def test_example_patch_fixture_applies_cleanly(self):
        result = apply_patch(example_diagram, example_patch)

        assert len(result.components) == len(example_diagram.components) + 1
        assert any(c.id == "comp-nat-gateway" for c in result.components)

        cloudwatch = next(c for c in result.components if c.id == "comp-cloudwatch")
        assert cloudwatch.element_type == "data_store"

        assert not any(tb.id == "tb-az2-implicita" for tb in result.trust_boundaries)
        rds_standby = next(c for c in result.components if c.id == "comp-rds-standby")
        assert rds_standby.trust_boundary == "tb-az1"
