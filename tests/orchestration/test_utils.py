"""Testes dos helpers puros da orquestração (US-2.1)."""
from __future__ import annotations

from extraction.schemas import (
    ArchitectureDiagram,
    Component,
    DataFlow,
    DiagramMetadata,
    TrustBoundary,
)
from knowledge.models import (
    KGQueryResult,
    MitigationResult,
    STRIDEResult,
    ThreatResult,
)
from orchestration.utils import (
    build_component_profile,
    component_crosses_boundary,
    render_kg_context,
)


def _diagram() -> ArchitectureDiagram:
    return ArchitectureDiagram(
        diagram_metadata=DiagramMetadata(
            cloud_provider="aws", region="us-east-1", extraction_confidence="alta"
        ),
        trust_boundaries=[
            TrustBoundary(id="tb-pub", name="Public", type="subnet", parent=None),
            TrustBoundary(id="tb-priv", name="Private", type="subnet", parent=None),
        ],
        components=[
            Component(
                id="c1", name="Gateway", aws_service="API Gateway",
                element_type="process", category=None, trust_boundary="tb-pub",
                instance_count=1,
            ),
            Component(
                id="c2", name="App", aws_service="Lambda",
                element_type="process", category=None, trust_boundary="tb-priv",
                instance_count=1,
            ),
            Component(
                id="c3", name="Cache", aws_service="ElastiCache",
                element_type="data_store", category=None, trust_boundary="tb-priv",
                instance_count=1,
            ),
        ],
        data_flows=[
            DataFlow(
                id="f1", source="c1", destination="c2", protocol="https",
                crosses_boundary=True, note=None,
            ),
            DataFlow(
                id="f2", source="c2", destination="c3", protocol="redis",
                crosses_boundary=False, note=None,
            ),
        ],
    )


def test_component_crosses_boundary_true():
    diagram = _diagram()
    assert component_crosses_boundary(diagram, "c1") is True  # origem de flow que cruza
    assert component_crosses_boundary(diagram, "c2") is True  # destino de flow que cruza


def test_component_crosses_boundary_false():
    diagram = _diagram()
    # c3 só aparece em f2 (interno) -> não cruza.
    assert component_crosses_boundary(diagram, "c3") is False


def test_build_component_profile_contem_campos():
    profile = build_component_profile(_diagram(), "c1")
    assert "Gateway" in profile
    assert "process" in profile
    assert "API Gateway" in profile
    assert "tb-pub" in profile
    assert "Cruza trust boundary: sim" in profile


def test_render_kg_context_vazio():
    kg = KGQueryResult(
        element_type="process", cloud_service=None, stride_results=[],
        total_threats=0, query_source="taxonomy",
    )
    assert "Nenhuma ameaça" in render_kg_context(kg)


def test_render_kg_context_trunca_em_6000():
    # Gera um KG grande o suficiente para ultrapassar 6000 caracteres.
    threats = [
        ThreatResult(
            id=f"t{i}", name=f"Ameaça {i}", severity="high",
            description="descrição longa " * 20,
        )
        for i in range(40)
    ]
    mitigations = [
        MitigationResult(
            id=f"m{i}", name=f"Mitigação {i}", control_type="preventive",
            description="mitigação longa " * 20,
        )
        for i in range(40)
    ]
    stride_results = [
        STRIDEResult(category="Spoofing", letter="S", threats=threats, mitigations=mitigations),
        STRIDEResult(category="Tampering", letter="T", threats=threats, mitigations=mitigations),
    ]
    kg = KGQueryResult(
        element_type="process", cloud_service="Lambda", stride_results=stride_results,
        total_threats=len(threats) * 2, query_source="both",
    )

    rendered = render_kg_context(kg)
    assert len(rendered) <= 6000
    # Não termina no meio de uma linha órfã: o corpo antes do marcador termina
    # em linha completa (o marcador começa com \n).
    assert "contexto truncado" in rendered
