"""Testes do nó retrieve_threats — cascata de fallback do KG (US-2.3)."""
from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from extraction.schemas import (
    ArchitectureDiagram,
    Component,
    DataFlow,
    DiagramMetadata,
    TrustBoundary,
)
from knowledge import fixtures as kg_fixtures
from knowledge.exceptions import ElementTypeNotFoundError
from orchestration.nodes import retrieve_threats


def _diagram(element_type: str = "data_store") -> ArchitectureDiagram:
    return ArchitectureDiagram(
        diagram_metadata=DiagramMetadata(
            cloud_provider="aws", region=None, extraction_confidence="alta"
        ),
        trust_boundaries=[TrustBoundary(id="tb", name="B", type="vpc", parent=None)],
        components=[
            Component(
                id="c1", name="Componente Teste", aws_service="Serviço X",
                element_type=element_type, category=None, trust_boundary="tb",
                instance_count=1,
            )
        ],
        data_flows=[
            DataFlow(
                id="f1", source="c1", destination="c1", protocol="x",
                crosses_boundary=False, note=None,
            )
        ],
    )


def _state(element_type: str = "data_store") -> dict:
    return {
        "diagram": _diagram(element_type),
        "components_queue": ["c1"],
        "kg_results": {},
    }


# ---------------------------------------------------------------------------
# Nó retrieve_threats
# ---------------------------------------------------------------------------


def test_fallback_para_fixture_quando_query_indisponivel():
    # Path "Dev 2 ainda não publicou a query real": get_stride_threats levanta
    # NotImplementedError -> retrieval cai no fixture get_fixture_for("data_store")
    # (T, R, I, D -> 8 threats no fixture real de Dev 2).
    with patch(
        "knowledge.query.get_stride_threats",
        side_effect=NotImplementedError,
    ):
        result = retrieve_threats(_state("data_store"))
    kg = result["kg_results"]["c1"]
    assert kg.total_threats > 0
    assert kg.total_threats == 8


def test_falha_infra_neo4j_propaga_nao_engole():
    # Falha de infra (Neo4j fora do ar) NÃO é capturada: propaga para o
    # service.py, que a converte em status="error". Travar cedo evita gastar
    # tokens de LLM num relatório sem grounding. Só ElementTypeNotFound e
    # ImportError/NotImplementedError são tratados; o resto sobe.
    with patch(
        "knowledge.query.get_stride_threats",
        side_effect=RuntimeError("Neo4j ServiceUnavailable"),
    ):
        with pytest.raises(RuntimeError, match="ServiceUnavailable"):
            retrieve_threats(_state("data_store"))


def test_element_type_not_found_nao_aborta(caplog):
    with patch(
        "knowledge.query.get_stride_threats",
        side_effect=ElementTypeNotFoundError("desconhecido"),
    ):
        with caplog.at_level(logging.WARNING):
            result = retrieve_threats(_state("data_store"))

    kg = result["kg_results"]["c1"]
    assert kg.stride_results == []
    assert kg.total_threats == 0
    assert any(
        "element type not found" in rec.message.lower()
        or "element type not found" in rec.getMessage().lower()
        for rec in caplog.records
    )


def test_log_retrieval_completed(caplog):
    with caplog.at_level(logging.INFO):
        retrieve_threats(_state("process"))
    mensagens = " ".join(rec.getMessage() for rec in caplog.records)
    assert "Retrieval completed" in mensagens
    assert "component=" in mensagens
    assert "element_type=" in mensagens
    assert "threats=" in mensagens


def test_dequeue_preservado():
    result = retrieve_threats(_state("process"))
    assert result["current_component_id"] == "c1"
    assert result["components_queue"] == []


# ---------------------------------------------------------------------------
# knowledge/fixtures.py
# ---------------------------------------------------------------------------


def test_fixture_process_tem_6_letras():
    kg = kg_fixtures.get_fixture_for("process")
    letras = {sr.letter for sr in kg.stride_results}
    assert letras == {"S", "T", "R", "I", "D", "E"}
    assert kg.total_threats == 12


def test_fixture_external_entity_S_e_R():
    kg = kg_fixtures.get_fixture_for("external_entity")
    letras = {sr.letter for sr in kg.stride_results}
    assert letras == {"S", "R"}


def test_fixture_tipo_invalido_levanta_keyerror():
    with pytest.raises(KeyError):
        kg_fixtures.get_fixture_for("tipo_invalido")
