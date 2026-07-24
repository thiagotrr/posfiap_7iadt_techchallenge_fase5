"""Testes do nó prepare_components — ordenação por element_type (US-2.2)."""
from __future__ import annotations

from extraction.schemas import (
    ArchitectureDiagram,
    Component,
    DataFlow,
    DiagramMetadata,
    TrustBoundary,
)
from orchestration.nodes import prepare_components


def _component(cid: str, element_type: str) -> Component:
    return Component(
        id=cid,
        name=f"Comp {cid}",
        aws_service=None,
        element_type=element_type,
        category=None,
        trust_boundary="tb",
        instance_count=1,
    )


def _diagram(components: list[Component]) -> ArchitectureDiagram:
    return ArchitectureDiagram(
        diagram_metadata=DiagramMetadata(
            cloud_provider="aws", region=None, extraction_confidence="média"
        ),
        trust_boundaries=[TrustBoundary(id="tb", name="B", type="vpc", parent=None)],
        components=components,
        data_flows=[
            DataFlow(
                id="f1", source=components[0].id, destination=components[0].id,
                protocol="x", crosses_boundary=False, note=None,
            )
        ],
    )


def test_fila_ordenada_por_element_type():
    # Componentes fora de ordem: external_entity e data_flow antes de process.
    diagram = _diagram(
        [
            _component("ext", "external_entity"),
            _component("flow", "data_flow"),
            _component("proc", "process"),
            _component("store", "data_store"),
        ]
    )
    result = prepare_components({"diagram": diagram})
    assert result["components_queue"] == ["proc", "store", "flow", "ext"]


def test_ordenacao_estavel_dentro_do_mesmo_tipo():
    # Dois process preservam a ordem original (sorted é estável).
    diagram = _diagram(
        [
            _component("p1", "process"),
            _component("s1", "data_store"),
            _component("p2", "process"),
        ]
    )
    result = prepare_components({"diagram": diagram})
    assert result["components_queue"] == ["p1", "p2", "s1"]


def test_acumuladores_inicializados():
    diagram = _diagram([_component("p1", "process")])
    result = prepare_components({"diagram": diagram})
    assert result["kg_results"] == {}
    assert result["component_analyses"] == {}
    assert result["hitl_approved"] is False  # Épico 3: hitl_review decide via interrupt
    assert result["report"] is None
    assert result["error"] is None
