"""Testes do generate_report enriquecido (US-4.2, Épico 4)."""
from __future__ import annotations

from extraction.schemas import (
    ArchitectureDiagram,
    Component,
    DataFlow,
    DiagramMetadata,
    TrustBoundary,
)
from orchestration.models import ComponentAnalysis, STRIDEThreatEntry
from orchestration.nodes import generate_report


def _entry(category, severity, name="t"):
    return STRIDEThreatEntry(
        category=category,
        threat_name=name,
        threat_description="d",
        severity=severity,
        mitigations=["m"],
        source="llm_only",
    )


def _analysis(component_id, entries):
    return ComponentAnalysis(
        component_id=component_id,
        component_name=f"Comp {component_id}",
        element_type="process",
        cloud_service="Lambda",
        trust_boundary="tb",
        stride_entries=entries,
        llm_reasoning="r",
        analyzed_at="2026-07-21T00:00:00Z",
    )


def _diagram():
    return ArchitectureDiagram(
        diagram_metadata=DiagramMetadata(
            cloud_provider="aws", region=None, extraction_confidence="alta"
        ),
        trust_boundaries=[TrustBoundary(id="tb", name="B", type="vpc", parent=None)],
        components=[
            Component(
                id=cid, name=f"Comp {cid}", aws_service="Lambda",
                element_type="process", category=None, trust_boundary="tb",
                instance_count=1,
            )
            for cid in ("c1", "c2", "c3")
        ],
        data_flows=[
            DataFlow(id="f1", source="c1", destination="c2", protocol="x",
                     crosses_boundary=False, note=None)
        ],
    )


def _state():
    # c1: 2 ameaças (S/critical, T/low) | c2: 1 (I/high) | c3: sem ameaças
    return {
        "diagram": _diagram(),
        "component_analyses": {
            "c1": _analysis("c1", [_entry("T", "low"), _entry("S", "critical")]),
            "c2": _analysis("c2", [_entry("I", "high")]),
            "c3": _analysis("c3", []),
        },
        "failed_component_ids": ["c3"],
    }


def test_risk_summary_enriquecido():
    report = generate_report(_state())["report"]
    rs = report.risk_summary
    assert rs["total_threats"] == 3
    assert rs["critical"] == 1 and rs["high"] == 1 and rs["low"] == 1
    assert rs["by_category"] == {"S": 1, "T": 1, "R": 0, "I": 1, "D": 0, "E": 0}
    assert rs["components_analyzed"] == 3
    assert rs["components_with_threats"] == 2
    assert rs["components_without_threats"] == 1
    assert rs["components_failed"] == 1


def test_stride_matrix():
    report = generate_report(_state())["report"]
    assert set(report.stride_matrix["S"]) == {"c1"}
    assert set(report.stride_matrix["I"]) == {"c2"}
    assert report.stride_matrix["D"] == []


def test_entries_ordenadas_por_severidade():
    report = generate_report(_state())["report"]
    c1 = next(a for a in report.component_analyses if a.component_id == "c1")
    # entradas entram como [low, critical] -> saem [critical, low]
    assert [e.severity for e in c1.stride_entries] == ["critical", "low"]


def test_report_serializa():
    report = generate_report(_state())["report"]
    from orchestration.models import STRIDEReport

    assert STRIDEReport.model_validate(report.model_dump()) == report
