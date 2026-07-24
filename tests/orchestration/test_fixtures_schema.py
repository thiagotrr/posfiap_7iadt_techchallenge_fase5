"""Testes dos fixtures de contrato e do snapshot JSON Schema (US-1.3, Épico 1)."""
from __future__ import annotations

import json
from pathlib import Path

from orchestration import fixtures
from orchestration.models import GraphStateResponse, STRIDEReport
from orchestration.schema_export import generate_schemas_v1

_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "orchestration" / "schemas_v1.json"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def test_example_stride_report_consistente():
    report = fixtures.example_stride_report()
    # Agregados batem com o conteúdo das análises.
    assert report.total_components == len(report.component_analyses)
    assert report.total_threats == sum(
        len(a.stride_entries) for a in report.component_analyses
    )
    # A matriz referencia apenas ids de componentes existentes.
    ids = {a.component_id for a in report.component_analyses}
    for componentes in report.stride_matrix.values():
        assert set(componentes) <= ids
    # risk_summary soma igual ao total de ameaças.
    assert sum(report.risk_summary.values()) == report.total_threats


def test_example_stride_report_roundtrip():
    report = fixtures.example_stride_report()
    assert STRIDEReport.model_validate(report.model_dump()) == report


def test_example_graph_state_usavel():
    state = fixtures.example_graph_state()
    assert state["report"] is not None
    assert state["components_queue"] == []
    assert set(state["component_analyses"]) == {"c1", "c2"}


def test_example_state_responses():
    running = fixtures.example_state_response_running()
    completed = fixtures.example_state_response_completed()
    assert running.status == "running"
    assert running.report is None
    assert completed.status == "completed"
    assert completed.report is not None
    # Serializam sem erro.
    assert GraphStateResponse.model_validate(completed.model_dump()) == completed


def test_example_diagram_valida_boundaries():
    # O model_validator de ArchitectureDiagram não deve levantar.
    diagram = fixtures.example_diagram()
    boundary_ids = {tb.id for tb in diagram.trust_boundaries}
    for component in diagram.components:
        assert component.trust_boundary in boundary_ids


# ---------------------------------------------------------------------------
# Snapshot JSON Schema
# ---------------------------------------------------------------------------


def test_schemas_v1_snapshot_atualizado():
    # Detecta drift: se os modelos mudaram, rode `python scripts/gen_schemas.py`.
    committed = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    current = generate_schemas_v1()
    assert committed == current, (
        "schemas_v1.json desatualizado — rode `python scripts/gen_schemas.py`"
    )


def test_schemas_v1_estrutura():
    schema = generate_schemas_v1()
    assert schema["version"] == "v1"
    assert "STRIDEReport" in schema
    assert "GraphStateResponse" in schema
    # STRIDEReport referencia ComponentAnalysis via $defs.
    assert "ComponentAnalysis" in schema["STRIDEReport"]["$defs"]
