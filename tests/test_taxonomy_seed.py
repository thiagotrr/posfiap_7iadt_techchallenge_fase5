"""
tests/test_taxonomy_seed.py

Testes unitários do seed da taxonomia STRIDE.
Verifica idempotência: executar o seed duas vezes não duplica nós.

Requer Neo4j acessível (testes de integração).
Marque com @pytest.mark.integration para separar dos testes unitários.
"""
import os
import pytest
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Testes unitários (sem Neo4j) — validam estrutura dos dados do seed
# ---------------------------------------------------------------------------

from knowledge.graph_schema import (
    STRIDE_MATRIX,
    ELEMENT_TYPES,
    STRIDE_LETTERS,
    REFERENCE_ARCHITECTURE_SERVICES,
)
from knowledge.taxonomy_seed import _ELEMENT_TYPES, _STRIDE_CATEGORIES, _THREATS, _MITIGATIONS

load_dotenv()

class TestSeedData:
    """Valida estrutura dos dados antes de tocar no Neo4j."""

    def test_element_types_count(self):
        assert len(_ELEMENT_TYPES) == 4

    def test_element_type_ids_match_schema(self):
        seed_ids = {et["id"] for et in _ELEMENT_TYPES}
        schema_ids = set(ELEMENT_TYPES)
        assert seed_ids == schema_ids

    def test_stride_categories_count(self):
        assert len(_STRIDE_CATEGORIES) == 6

    def test_stride_categories_letters(self):
        letters = {cat["letter"] for cat in _STRIDE_CATEGORIES}
        assert letters == set(STRIDE_LETTERS)

    def test_threats_minimum_two_per_category(self):
        """Ao menos 2 Threats por categoria STRIDE (≥ 12 total)."""
        from collections import Counter
        counts = Counter(t["category_id"] for t in _THREATS)
        for cat in _STRIDE_CATEGORIES:
            assert counts[cat["id"]] >= 2, f"Category {cat['id']} has < 2 threats"

    def test_threats_total_minimum(self):
        assert len(_THREATS) >= 12

    def test_mitigations_one_per_threat(self):
        """Ao menos 1 Mitigation por Threat."""
        from collections import Counter
        threat_ids = {t["id"] for t in _THREATS}
        mit_threat_ids = Counter(m["threat_id"] for m in _MITIGATIONS)
        for tid in threat_ids:
            assert mit_threat_ids[tid] >= 1, f"Threat {tid} has no mitigation"

    def test_severity_values_valid(self):
        valid = {"critical", "high", "medium", "low"}
        for t in _THREATS:
            assert t["severity"] in valid, f"Invalid severity '{t['severity']}' in threat {t['id']}"

    def test_control_type_values_valid(self):
        valid = {"preventive", "detective", "corrective"}
        for m in _MITIGATIONS:
            assert m["control_type"] in valid, f"Invalid control_type in mitigation {m['id']}"

    def test_stride_matrix_coverage(self):
        """Todos os element_types devem ter pelo menos 1 categoria STRIDE."""
        for et in ELEMENT_TYPES:
            assert et in STRIDE_MATRIX
            assert len(STRIDE_MATRIX[et]) > 0

    def test_reference_architecture_services_count(self):
        assert len(REFERENCE_ARCHITECTURE_SERVICES) == 11  # + External Entity = 12 no seed

    def test_reference_architecture_element_types_valid(self):
        valid = set(ELEMENT_TYPES)
        for svc in REFERENCE_ARCHITECTURE_SERVICES:
            assert svc["element_type"] in valid, (
                f"Service {svc['name']} has invalid element_type '{svc['element_type']}'"
            )


# ---------------------------------------------------------------------------
# Testes de integração (com Neo4j real)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestSeedIdempotency:
    """Verifica que executar o seed duas vezes não duplica nós."""

    @pytest.fixture(scope="class")
    def driver(self):
        """Cria driver para testes de integração."""
        from knowledge.graph_client import get_driver

        yield get_driver()

    def _count_nodes(self, session, label: str) -> int:
        result = session.run(f"MATCH (n:{label}) RETURN count(n) AS cnt")
        return result.single()["cnt"]

    def test_seed_idempotency_element_types(self, driver):
        """Executar seed 2x não duplica ElementType."""
        from knowledge.taxonomy_seed import run_seed

        run_seed(driver)
        with driver.session() as session:
            count_after_first = self._count_nodes(session, "ElementType")

        run_seed(driver)
        with driver.session() as session:
            count_after_second = self._count_nodes(session, "ElementType")

        assert count_after_first == count_after_second == 4

    def test_seed_populates_all_stride_categories(self, driver):
        from knowledge.taxonomy_seed import run_seed
        run_seed(driver)
        with driver.session() as session:
            count = self._count_nodes(session, "STRIDECategory")
        assert count == 6

    def test_seed_populates_minimum_threats(self, driver):
        from knowledge.taxonomy_seed import run_seed
        run_seed(driver)
        with driver.session() as session:
            count = self._count_nodes(session, "Threat")
        assert count >= 12

    def test_seed_populates_cloud_services(self, driver):
        from knowledge.taxonomy_seed import run_seed
        run_seed(driver)
        with driver.session() as session:
            count = self._count_nodes(session, "CloudService")
        # 11 serviços AWS + 1 External Entity genérico
        assert count >= 12

    def test_stride_matrix_relationships_exist(self, driver):
        """Verifica que process tem 6 categorias STRIDE."""
        from knowledge.taxonomy_seed import run_seed
        run_seed(driver)
        with driver.session() as session:
            result = session.run(
                "MATCH (et:ElementType {id: 'process'})-[:SUSCETIVEL_A]->(sc:STRIDECategory) "
                "RETURN count(sc) AS cnt"
            )
            count = result.single()["cnt"]
        assert count == 6

    def test_data_store_has_4_categories(self, driver):
        from knowledge.taxonomy_seed import run_seed
        run_seed(driver)
        with driver.session() as session:
            result = session.run(
                "MATCH (et:ElementType {id: 'data_store'})-[:SUSCETIVEL_A]->(sc:STRIDECategory) "
                "RETURN count(sc) AS cnt"
            )
            count = result.single()["cnt"]
        assert count == 4

    def test_external_entity_has_2_categories(self, driver):
        from knowledge.taxonomy_seed import run_seed
        run_seed(driver)
        with driver.session() as session:
            result = session.run(
                "MATCH (et:ElementType {id: 'external_entity'})-[:SUSCETIVEL_A]->(sc:STRIDECategory) "
                "RETURN count(sc) AS cnt"
            )
            count = result.single()["cnt"]
        assert count == 2
