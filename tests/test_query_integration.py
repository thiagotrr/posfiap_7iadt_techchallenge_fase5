"""Testes de integração de get_stride_threats contra Neo4j real."""

import os

import pytest
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

from knowledge.query import get_stride_threats
from knowledge.taxonomy_seed import run_seed


@pytest.fixture(scope="module")
def seeded_driver():
    password = os.getenv("NEO4J_PASSWORD")
    if not password:
        pytest.skip("NEO4J_PASSWORD não configurada para o teste de integração")

    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        auth=(os.getenv("NEO4J_USER", "neo4j"), password),
    )
    try:
        driver.verify_connectivity()
    except Exception as exc:
        driver.close()
        pytest.skip(f"Neo4j indisponível para o teste de integração: {exc}")

    run_seed(driver)
    yield driver
    driver.close()


@pytest.mark.integration
@pytest.mark.parametrize(
    ("element_type", "expected_letters"),
    [
        ("process", ["S", "T", "R", "I", "D", "E"]),
        ("external_entity", ["S", "R"]),
        ("data_store", ["T", "R", "I", "D"]),
    ],
)
def test_seeded_taxonomy_category_matrix(
    seeded_driver,
    element_type,
    expected_letters,
):
    result = get_stride_threats(element_type, driver=seeded_driver)

    assert [item.letter for item in result.stride_results] == expected_letters
    assert result.query_source == "taxonomy"
    assert result.total_threats == len(expected_letters) * 2
