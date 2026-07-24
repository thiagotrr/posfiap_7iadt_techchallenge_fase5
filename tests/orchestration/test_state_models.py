"""Testes dos modelos de estado e output do grafo (US-1.1, Épico 1)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

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
from orchestration.models import (
    ComponentAnalysis,
    GraphStateResponse,
    STRIDEReport,
    STRIDEThreatEntry,
)
from orchestration.state import GraphState


def _sample_threat_entry() -> STRIDEThreatEntry:
    return STRIDEThreatEntry(
        category="S",  # category_name derivado pelo validator
        threat_name="Falsificação de identidade no gateway",
        threat_description="Ator externo se passa por serviço legítimo.",
        severity="high",
        mitigations=["mTLS entre serviços", "Rotação de credenciais"],
        source="taxonomy",
    )


def _sample_component_analysis() -> ComponentAnalysis:
    return ComponentAnalysis(
        component_id="c1",
        component_name="API Gateway",
        element_type="process",
        cloud_service="AWS API Gateway",
        trust_boundary="tb-public",
        stride_entries=[_sample_threat_entry()],
        llm_reasoning="Componente cruza fronteira pública; foco em spoofing.",
        analyzed_at="2026-07-15T10:00:00Z",
    )


def _sample_report() -> STRIDEReport:
    return STRIDEReport(
        diagram_provider="aws",
        total_components=1,
        total_threats=1,
        generated_at="2026-07-15T10:05:00Z",
        component_analyses=[_sample_component_analysis()],
        stride_matrix={"S": ["c1"], "T": [], "R": [], "I": [], "D": [], "E": []},
        risk_summary={"critical": 0, "high": 1, "medium": 0, "low": 0},
    )


def test_stride_report_roundtrip_sem_perda():
    report = _sample_report()
    dumped = report.model_dump()
    restored = STRIDEReport.model_validate(dumped)
    assert restored == report
    assert restored.model_dump() == dumped


def test_component_analysis_aceita_stride_entries_vazio():
    analysis = ComponentAnalysis(
        component_id="c2",
        component_name="S3 Bucket",
        element_type="data_store",
        cloud_service="AWS S3",
        trust_boundary="tb-private",
        stride_entries=[],
        llm_reasoning="Sem ameaças relevantes identificadas.",
        analyzed_at="2026-07-15T10:01:00Z",
    )
    assert analysis.stride_entries == []


def test_graph_state_response_serializa_com_report_none():
    response = GraphStateResponse(
        thread_id="thread-abc",
        status="running",
        components_analyzed_count=3,
        components_total=14,
        hitl_summary=None,
        report=None,
    )
    dumped = response.model_dump()
    assert dumped["report"] is None
    assert dumped["status"] == "running"
    restored = GraphStateResponse.model_validate(dumped)
    assert restored == response


def test_category_name_derivado_de_category():
    entry = STRIDEThreatEntry(
        category="T",
        threat_name="Adulteração",
        threat_description="...",
        severity="medium",
        mitigations=[],
        source="taxonomy",
    )
    assert entry.category_name == "Tampering"


def test_category_name_input_e_sempre_sobrescrito():
    # Mesmo passando um valor errado, o validator deriva de `category`.
    entry = STRIDEThreatEntry(
        category="I",
        category_name="VALOR ERRADO",
        threat_name="Vazamento",
        threat_description="...",
        severity="high",
        mitigations=[],
        source="both",
    )
    assert entry.category_name == "Information Disclosure"


def test_category_fora_do_literal_falha():
    with pytest.raises(ValidationError):
        STRIDEThreatEntry(
            category="X",
            threat_name="Inválida",
            threat_description="...",
            severity="low",
            mitigations=[],
            source="llm_only",
        )


def test_graph_state_response_novos_campos_preenchidos():
    response = GraphStateResponse(
        thread_id="t-1",
        status="running",
        components_analyzed_count=2,
        components_total=5,
        analyzed_component_ids=["c1", "c2"],
        components_failed_count=1,
        hitl_summary=None,
        report=None,
    )
    restored = GraphStateResponse.model_validate(response.model_dump())
    assert restored == response
    assert restored.analyzed_component_ids == ["c1", "c2"]
    assert restored.components_failed_count == 1


def test_graph_state_response_novos_campos_defaults():
    response = GraphStateResponse(
        thread_id="t-2",
        status="completed",
        components_analyzed_count=0,
        components_total=0,
    )
    assert response.analyzed_component_ids == []
    assert response.components_failed_count == 0
    restored = GraphStateResponse.model_validate(response.model_dump())
    assert restored == response


def test_graph_state_type_hints_resolvem_em_runtime():
    # LangGraph chama get_type_hints(GraphState) ao montar StateGraph(...).
    # Regressão: as anotações (strings, por __future__.annotations) precisam
    # resolver em runtime — todos os nomes referenciados devem existir no
    # namespace do módulo, não só sob TYPE_CHECKING.
    from typing import get_type_hints

    hints = get_type_hints(GraphState)
    assert "component_analyses" in hints
    assert "report" in hints
    assert "diagram" in hints


def test_graph_state_utilizavel_como_dict():
    diagram = ArchitectureDiagram(
        diagram_metadata=DiagramMetadata(
            cloud_provider="aws", region="us-east-1", extraction_confidence="alta"
        ),
        trust_boundaries=[
            TrustBoundary(id="tb-public", name="Public", type="vpc", parent=None)
        ],
        components=[
            Component(
                id="c1",
                name="API Gateway",
                aws_service="AWS API Gateway",
                element_type="process",
                category=None,
                trust_boundary="tb-public",
                instance_count=1,
            )
        ],
        data_flows=[
            DataFlow(
                id="f1",
                source="c1",
                destination="c1",
                protocol="https",
                crosses_boundary=True,
                note=None,
            )
        ],
    )
    kg_result = KGQueryResult(
        element_type="process",
        cloud_service="AWS API Gateway",
        stride_results=[
            STRIDEResult(
                category="Spoofing",
                letter="S",
                threats=[
                    ThreatResult(
                        id="t1", name="Spoofing", description="...", severity="high"
                    )
                ],
                mitigations=[
                    MitigationResult(
                        id="m1", name="mTLS", description="...", control_type="preventive"
                    )
                ],
            )
        ],
        total_threats=1,
        query_source="taxonomy",
    )

    state: GraphState = {
        "diagram": diagram,
        "components_queue": ["c1"],
        "current_component_id": None,
        "kg_results": {"c1": kg_result},
        "component_analyses": {},
        "chat_history": [],
        "hitl_feedback": None,
        "hitl_approved": False,
        "report": None,
        "error": None,
    }

    assert state["components_queue"] == ["c1"]
    assert state["kg_results"]["c1"].total_threats == 1
    assert state["diagram"].diagram_metadata.cloud_provider == "aws"
    assert state["report"] is None
