"""Fixtures compartilhados dos testes de orquestração.

Mock autouse de `knowledge.query.get_stride_threats`: os testes unitários NÃO
devem depender de um Neo4j de pé. Por padrão a query delega aos fixtures
determinísticos do Dev 2 (`knowledge.fixtures.get_fixture_for`).

Testes que exercitam caminhos de erro (Neo4j fora do ar, ElementTypeNotFound,
Dev 2 ainda não publicou) re-patcham `knowledge.query.get_stride_threats` no
próprio corpo — o `with patch(...)` interno tem precedência sobre este autouse.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _mock_kg_query():
    from knowledge.fixtures import get_fixture_for

    def _fake(element_type, cloud_service=None, driver=None):
        return get_fixture_for(element_type)

    with patch("knowledge.query.get_stride_threats", side_effect=_fake):
        yield
