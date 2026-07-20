"""
knowledge/query.py

Interface pública de query ao Knowledge Graph STRIDE.

Combina a taxonomia determinística com o enriquecimento por serviço gravado
pelo pipeline de ingestão, mantendo o contrato publicado no Épico 1.
"""

from __future__ import annotations

import logging
from contextlib import AbstractContextManager
from typing import Optional

from neo4j import Driver

from knowledge.exceptions import ElementTypeNotFoundError
from knowledge.graph_client import get_session
from knowledge.graph_schema import (
    CLOUD_SERVICES,
    NODE_CLOUD_SERVICE,
    NODE_ELEMENT_TYPE,
    NODE_MITIGATION,
    NODE_SOURCE,
    NODE_STRIDE_CATEGORY,
    NODE_THREAT,
    REL_COVERS_CATEGORY,
    REL_COVERS_SERVICE,
    REL_HAS_SPECIFIC_MITIGATION,
    REL_HAS_SPECIFIC_THREAT,
    REL_INCLUI_AMEACA,
    REL_INSTANCIA_DE,
    REL_MITIGADA_POR,
    REL_SUSCETIVEL_A,
    STRIDE_LETTERS,
)
from knowledge.models import (
    KGQueryResult,
    MitigationResult,
    STRIDEResult,
    ThreatResult,
)

logger = logging.getLogger(__name__)

_ELEMENT_TYPE_EXISTS_QUERY = f"""
MATCH (element:{NODE_ELEMENT_TYPE} {{id: $element_type}})
RETURN element.id AS element_type
"""

_TAXONOMY_QUERY = f"""
MATCH (element:{NODE_ELEMENT_TYPE} {{id: $element_type}})
      -[:{REL_SUSCETIVEL_A}]->(category:{NODE_STRIDE_CATEGORY})
      -[:{REL_INCLUI_AMEACA}]->(threat:{NODE_THREAT})
OPTIONAL MATCH (threat)-[:{REL_MITIGADA_POR}]->(mitigation:{NODE_MITIGATION})
RETURN category.letter AS category_letter,
       category.name AS category_name,
       threat.id AS threat_id,
       threat.name AS threat_name,
       threat.description AS threat_description,
       threat.severity AS threat_severity,
       mitigation.id AS mitigation_id,
       mitigation.name AS mitigation_name,
       mitigation.description AS mitigation_description,
       mitigation.control_type AS mitigation_control_type
"""

_ENRICHMENT_QUERY = f"""
MATCH (service:{NODE_CLOUD_SERVICE} {{name: $cloud_service}})
      -[:{REL_INSTANCIA_DE}]->(element:{NODE_ELEMENT_TYPE} {{id: $element_type}})
MATCH (element)-[:{REL_SUSCETIVEL_A}]->(category:{NODE_STRIDE_CATEGORY})
      -[:{REL_INCLUI_AMEACA}]->(threat:{NODE_THREAT})
MATCH (service)-[:{REL_HAS_SPECIFIC_THREAT}]->(threat)
MATCH (source:{NODE_SOURCE})-[:{REL_COVERS_SERVICE}]->(service)
MATCH (source)-[:{REL_COVERS_CATEGORY}]->(category)
OPTIONAL MATCH (threat)-[:{REL_MITIGADA_POR}]->(mitigation:{NODE_MITIGATION})
      <-[:{REL_HAS_SPECIFIC_MITIGATION}]-(service)
RETURN category.letter AS category_letter,
       category.name AS category_name,
       threat.id AS threat_id,
       threat.name AS threat_name,
       threat.description AS threat_description,
       threat.severity AS threat_severity,
       mitigation.id AS mitigation_id,
       mitigation.name AS mitigation_name,
       mitigation.description AS mitigation_description,
       mitigation.control_type AS mitigation_control_type
"""


def get_stride_threats(
    element_type: str,
    cloud_service: Optional[str] = None,
    driver: Optional[Driver] = None,
) -> KGQueryResult:
    """
    Retorna as ameaças e mitigações STRIDE para um tipo de elemento,
    opcionalmente enriquecidas com dados específicos do serviço de nuvem.

    Args:
        element_type: Tipo de elemento STRIDE.
            Valores aceitos: "process", "data_store", "data_flow", "external_entity".
        cloud_service: Nome canônico do serviço de nuvem (ex: "RDS", "S3").
            None = retorna apenas a taxonomia base.
        driver: Driver Neo4j. Se None, usa o Singleton de graph_client.

    Returns:
        KGQueryResult com as categorias STRIDE aplicáveis, ameaças e mitigações.

    Raises:
        ElementTypeNotFoundError: Se element_type não existir no KG.
    """
    canonical_service = (
        CLOUD_SERVICES.get(cloud_service, cloud_service)
        if cloud_service is not None
        else None
    )
    categories: dict[str, dict] = {}

    with _session_context(driver) as session:
        if session.run(
            _ELEMENT_TYPE_EXISTS_QUERY,
            element_type=element_type,
        ).single() is None:
            logger.warning(
                "KG query — element type not found: %s",
                element_type,
            )
            raise ElementTypeNotFoundError(element_type)

        taxonomy_rows = list(
            session.run(_TAXONOMY_QUERY, element_type=element_type)
        )
        _merge_rows(categories, taxonomy_rows)

        enrichment_rows = []
        if canonical_service is not None:
            enrichment_rows = list(
                session.run(
                    _ENRICHMENT_QUERY,
                    element_type=element_type,
                    cloud_service=canonical_service,
                )
            )
            _merge_rows(categories, enrichment_rows)

    has_taxonomy = bool(taxonomy_rows)
    has_enrichment = bool(enrichment_rows)
    if has_taxonomy and has_enrichment:
        query_source = "both"
    elif has_enrichment:
        query_source = "enriched"
    else:
        query_source = "taxonomy"

    stride_results = _build_stride_results(categories)
    result = KGQueryResult(
        element_type=element_type,
        cloud_service=canonical_service,
        stride_results=stride_results,
        total_threats=sum(len(item.threats) for item in stride_results),
        query_source=query_source,
    )
    logger.info(
        "KG query executed — element_type=%s service=%s results=%d source=%s",
        element_type,
        canonical_service,
        result.total_threats,
        result.query_source,
    )
    return result


def _session_context(driver: Optional[Driver]) -> AbstractContextManager:
    """Usa o driver injetado em testes ou o Singleton da aplicação."""
    if driver is not None:
        return driver.session()
    return get_session()


def _merge_rows(categories: dict[str, dict], rows: list) -> None:
    """Agrupa linhas Neo4j por categoria e remove duplicatas por id."""
    for row in rows:
        letter = row["category_letter"]
        category = categories.setdefault(
            letter,
            {
                "name": row["category_name"],
                "threats": {},
                "mitigations": {},
            },
        )

        threat_id = row["threat_id"]
        if threat_id is not None:
            category["threats"][threat_id] = ThreatResult(
                id=threat_id,
                name=row["threat_name"],
                description=row["threat_description"],
                severity=row["threat_severity"],
            )

        mitigation_id = row["mitigation_id"]
        if mitigation_id is not None:
            category["mitigations"][mitigation_id] = MitigationResult(
                id=mitigation_id,
                name=row["mitigation_name"],
                description=row["mitigation_description"],
                control_type=row["mitigation_control_type"],
            )


def _build_stride_results(categories: dict[str, dict]) -> list[STRIDEResult]:
    letter_order = {letter: index for index, letter in enumerate(STRIDE_LETTERS)}
    return [
        STRIDEResult(
            category=categories[letter]["name"],
            letter=letter,
            threats=list(categories[letter]["threats"].values()),
            mitigations=list(categories[letter]["mitigations"].values()),
        )
        for letter in sorted(
            categories,
            key=lambda item: letter_order.get(item, len(letter_order)),
        )
    ]
