"""Testes do skeleton do grafo LangGraph (US-1.2, Épico 1).

Valida a topologia e o fluxo end-to-end com nós mock, antes das integrações
reais (Neo4j/LLM) da Semana 2.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from extraction.schemas import (
    ArchitectureDiagram,
    Component,
    DataFlow,
    DiagramMetadata,
    TrustBoundary,
)
from langgraph.types import Command

from orchestration.graph import build_graph, get_compiled_graph
from orchestration.llm_client import LLMAnalysisClient
from orchestration.models import STRIDEReport
from orchestration.nodes import (
    check_iteration,
    generate_report,
    generate_threats,
    prepare_components,
    retrieve_threats,
    route_after_hitl,
)

# US-2.4: generate_threats agora chama o LLM. Mockamos analyze() em todo este
# módulo para validar a TOPOLOGIA do grafo sem chamada real de rede. Uma ameaça
# por componente (category=S, severity=medium) mantém as asserções de matriz/risco.
_MOCK_LLM_JSON = json.dumps(
    [
        {
            "category": "S",
            "threat_name": "[MOCK] Spoofing",
            "threat_description": "Ameaça mock para teste de topologia.",
            "severity": "medium",
            "mitigations": ["mitigação mock"],
            "source": "llm_only",
        }
    ]
)


@pytest.fixture(autouse=True)
def _mock_llm_analyze():
    with patch.object(LLMAnalysisClient, "analyze", return_value=_MOCK_LLM_JSON):
        yield


def _diagram(n: int = 3) -> ArchitectureDiagram:
    return ArchitectureDiagram(
        diagram_metadata=DiagramMetadata(
            cloud_provider="aws", region="us-east-1", extraction_confidence="alta"
        ),
        trust_boundaries=[
            TrustBoundary(id="tb-public", name="Public", type="vpc", parent=None)
        ],
        components=[
            Component(
                id=f"c{i}",
                name=f"Componente {i}",
                aws_service="AWS Lambda",
                element_type="process",
                category=None,
                trust_boundary="tb-public",
                instance_count=1,
            )
            for i in range(1, n + 1)
        ],
        data_flows=[
            DataFlow(
                id="f1",
                source="c1",
                destination=f"c{n}",
                protocol="https",
                crosses_boundary=False,
                note=None,
            )
        ],
    )


def _initial_state(diagram: ArchitectureDiagram) -> dict:
    # prepare_components reinicializa os acumuladores; basta o diagrama.
    return {"diagram": diagram}


def _config(thread_id: str) -> dict:
    # O grafo executa ~2N+3 nós (N = componentes). O default do LangGraph é 25;
    # o diagrama de referência tem 14 componentes (~31 passos). run_analysis()
    # (Épico 4) deverá dimensionar recursion_limit pelo nº de componentes.
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": 100}


# ---------------------------------------------------------------------------
# Compilação / singleton
# ---------------------------------------------------------------------------


def test_build_graph_compila():
    graph = build_graph()
    assert graph is not None
    # Duas chamadas produzem instâncias distintas.
    assert build_graph() is not graph


def test_get_compiled_graph_e_singleton():
    assert get_compiled_graph() is get_compiled_graph()


# ---------------------------------------------------------------------------
# Nós (unitários)
# ---------------------------------------------------------------------------


def test_prepare_components_enfileira_todos():
    state = _initial_state(_diagram(3))
    result = prepare_components(state)
    assert result["components_queue"] == ["c1", "c2", "c3"]
    assert result["component_analyses"] == {}
    assert result["kg_results"] == {}
    # Épico 3: inicia não aprovado; o hitl_review decide via interrupt/resume.
    assert result["hitl_approved"] is False


def test_retrieve_threats_desenfileira_e_adiciona_kg():
    state = {
        "diagram": _diagram(2),
        "components_queue": ["c1", "c2"],
        "kg_results": {},
    }
    # Query real de Dev 2 indisponível neste unit test -> mockamos
    # NotImplementedError para exercitar o fallback de fixture (determinístico,
    # sem Neo4j). O diagrama usa element_type="process" -> fixture de 12 ameaças.
    with patch("knowledge.query.get_stride_threats", side_effect=NotImplementedError):
        result = retrieve_threats(state)
    assert result["current_component_id"] == "c1"
    assert result["components_queue"] == ["c2"]
    assert "c1" in result["kg_results"]
    assert result["kg_results"]["c1"].total_threats == 12


def test_generate_threats_produz_component_analysis():
    state = {
        "diagram": _diagram(1),
        "current_component_id": "c1",
        "kg_results": {},
        "component_analyses": {},
    }
    result = generate_threats(state)
    analysis = result["component_analyses"]["c1"]
    assert analysis.component_id == "c1"
    assert len(analysis.stride_entries) == 1


def test_check_iteration_roteia_por_fila():
    assert check_iteration({"components_queue": ["c2"], "component_analyses": {}}) == (
        "retrieve_threats"
    )
    assert check_iteration({"components_queue": [], "component_analyses": {}}) == (
        "hitl_review"
    )


def test_route_after_hitl():
    assert route_after_hitl({"hitl_approved": True}) == "generate_report"
    assert route_after_hitl({"hitl_approved": False}) == "refine_analysis"


def test_generate_report_agrega_matriz_e_risco():
    diagram = _diagram(2)
    # Roda prepare + retrieve/generate manualmente para popular analyses.
    state: dict = {"diagram": diagram}
    state.update(prepare_components(state))
    for _ in range(2):
        state.update(retrieve_threats(state))
        state.update(generate_threats(state))

    result = generate_report(state)
    report: STRIDEReport = result["report"]
    assert report.total_components == 2
    assert report.total_threats == 2
    # Mock gera categoria "S" para ambos os componentes.
    assert set(report.stride_matrix["S"]) == {"c1", "c2"}
    assert report.risk_summary["medium"] == 2


# ---------------------------------------------------------------------------
# End-to-end
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n", [1, 3, 14])
def test_grafo_end_to_end(n: int):
    # Épico 3: o grafo PAUSA no hitl_review; aprova-se via Command(resume=...).
    graph = build_graph()
    cfg = _config(f"t-{n}")

    graph.invoke(_initial_state(_diagram(n)), config=cfg)
    assert graph.get_state(cfg).next == ("hitl_review",)  # pausado

    final = graph.invoke(Command(resume={"action": "approve"}), config=cfg)

    # .get(): LangGraph não materializa canais None (error nunca foi setado).
    assert final.get("error") is None
    assert len(final["components_queue"]) == 0
    assert len(final["component_analyses"]) == n

    report: STRIDEReport = final["report"]
    assert report is not None
    assert report.total_components == n
    assert report.total_threats == n
    assert report.diagram_provider == "aws"


def test_grafo_end_to_end_serializa_report():
    graph = build_graph()
    cfg = _config("t-serial")
    graph.invoke(_initial_state(_diagram(2)), config=cfg)
    final = graph.invoke(Command(resume={"action": "approve"}), config=cfg)
    dumped = final["report"].model_dump()
    restored = STRIDEReport.model_validate(dumped)
    assert restored == final["report"]
