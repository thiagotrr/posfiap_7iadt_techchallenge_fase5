"""Testes dos templates de prompt e do schema de saída (US-2.1)."""
from __future__ import annotations

import json

from knowledge.models import (
    KGQueryResult,
    MitigationResult,
    STRIDEResult,
    ThreatResult,
)
from orchestration import fixtures
from orchestration.prompts import (
    REFINEMENT_USER_TEMPLATE,
    STRIDE_ANALYSIS_USER_TEMPLATE,
    stride_entries_json_schema,
)
from orchestration.utils import build_component_profile, render_kg_context


def _kg_exemplo() -> KGQueryResult:
    return KGQueryResult(
        element_type="process",
        cloud_service="API Gateway",
        stride_results=[
            STRIDEResult(
                category="Spoofing",
                letter="S",
                threats=[
                    ThreatResult(id="t1", name="Spoofing de token", description="...", severity="high")
                ],
                mitigations=[
                    MitigationResult(id="m1", name="mTLS", description="...", control_type="preventive")
                ],
            )
        ],
        total_threats=1,
        query_source="taxonomy",
    )


def test_stride_analysis_template_renderiza_sem_placeholder_residual():
    diagram = fixtures.example_diagram()
    schema_str = json.dumps(stride_entries_json_schema(), ensure_ascii=False)
    texto = STRIDE_ANALYSIS_USER_TEMPLATE.format(
        component_profile=build_component_profile(diagram, "c1"),
        kg_context=render_kg_context(_kg_exemplo()),
        json_schema=schema_str,
    )
    for placeholder in ("{component_profile}", "{kg_context}", "{json_schema}"):
        assert placeholder not in texto
    assert "API Gateway" in texto
    assert "Spoofing de token" in texto


def test_refinement_template_renderiza_sem_placeholder_residual():
    schema_str = json.dumps(stride_entries_json_schema(), ensure_ascii=False)
    texto = REFINEMENT_USER_TEMPLATE.format(
        current_analysis="[]",
        user_feedback="Adicionar ameaça de repúdio.",
        json_schema=schema_str,
    )
    for placeholder in ("{current_analysis}", "{user_feedback}", "{json_schema}"):
        assert placeholder not in texto
    assert "repúdio" in texto


def test_stride_entries_json_schema_e_lista():
    schema = stride_entries_json_schema()
    assert isinstance(schema, dict)
    # É schema de lista -> tem "items" no topo.
    assert "items" in schema
    assert schema.get("type") == "array"


def test_stride_entries_json_schema_category_enum():
    schema = stride_entries_json_schema()
    entry_schema = schema["$defs"]["STRIDEThreatEntry"]
    category_enum = entry_schema["properties"]["category"]["enum"]
    assert set(category_enum) == {"S", "T", "R", "I", "D", "E"}
