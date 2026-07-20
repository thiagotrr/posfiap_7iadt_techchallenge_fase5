"""Persistência do conteúdo classificado no Knowledge Graph Neo4j."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from neo4j import Driver

from knowledge.crawler.crawler import CrawledDocument
from knowledge.graph_schema import (
    NODE_CLOUD_SERVICE,
    NODE_SOURCE,
    NODE_STRIDE_CATEGORY,
    REL_COVERS_CATEGORY,
    REL_COVERS_SERVICE,
    REL_HAS_SPECIFIC_MITIGATION,
    REL_HAS_SPECIFIC_THREAT,
    REL_INCLUI_AMEACA,
    REL_MITIGADA_POR,
    REL_REFERENCIADA_EM,
)
from knowledge.ingestion.classifier import ClassificationResult

logger = logging.getLogger(__name__)


@dataclass
class LoadResult:
    source_node_id: str
    services_linked: int
    categories_linked: int


class KGLoader:
    """Carrega um documento e seus vínculos usando operações idempotentes."""

    def load(
        self,
        doc: CrawledDocument,
        classification: ClassificationResult,
        driver: Driver,
    ) -> LoadResult:
        source_id = f"source-{doc.content_hash}"
        services = list(dict.fromkeys(classification.relevant_services))
        tags = list(dict.fromkeys(classification.stride_tags))

        with driver.session() as session:
            session.run(
                f"""
                MERGE (source:{NODE_SOURCE} {{id: $id}})
                SET source.url = $url,
                    source.title = $title,
                    source.crawled_at = $crawled_at,
                    source.stride_tags = $stride_tags,
                    source.content_hash = $content_hash,
                    source.source_name = $source_name,
                    source.provider = $provider,
                    source.text_content = $text_content
                """,
                id=source_id,
                url=doc.url,
                title=doc.title,
                crawled_at=doc.crawled_at,
                stride_tags=tags,
                content_hash=doc.content_hash,
                source_name=doc.source_name,
                provider=doc.provider,
                text_content=doc.text_content,
            ).consume()

            service_record = session.run(
                f"""
                MATCH (source:{NODE_SOURCE} {{id: $source_id}})
                UNWIND $services AS service_name
                MATCH (service:{NODE_CLOUD_SERVICE} {{name: service_name}})
                MERGE (source)-[:{REL_COVERS_SERVICE}]->(service)
                RETURN count(DISTINCT service) AS linked
                """,
                source_id=source_id,
                services=services,
            ).single()

            category_record = session.run(
                f"""
                MATCH (source:{NODE_SOURCE} {{id: $source_id}})
                UNWIND $tags AS tag
                MATCH (category:{NODE_STRIDE_CATEGORY} {{letter: tag}})
                MERGE (source)-[:{REL_COVERS_CATEGORY}]->(category)
                RETURN count(DISTINCT category) AS linked
                """,
                source_id=source_id,
                tags=tags,
            ).single()

            session.run(
                f"""
                MATCH (source:{NODE_SOURCE} {{id: $source_id}})
                UNWIND $services AS service_name
                MATCH (service:{NODE_CLOUD_SERVICE} {{name: service_name}})
                UNWIND $tags AS tag
                MATCH (category:{NODE_STRIDE_CATEGORY} {{letter: tag}})
                      -[:{REL_INCLUI_AMEACA}]->(threat)
                MERGE (service)-[:{REL_HAS_SPECIFIC_THREAT}]->(threat)
                WITH source, service, threat
                OPTIONAL MATCH (threat)-[:{REL_MITIGADA_POR}]->(mitigation)
                FOREACH (_ IN CASE WHEN mitigation IS NULL THEN [] ELSE [1] END |
                    MERGE (service)-[:{REL_HAS_SPECIFIC_MITIGATION}]->(mitigation)
                    MERGE (mitigation)-[:{REL_REFERENCIADA_EM}]->(source)
                )
                """,
                source_id=source_id,
                services=services,
                tags=tags,
            ).consume()

        result = LoadResult(
            source_node_id=source_id,
            services_linked=_linked_count(service_record),
            categories_linked=_linked_count(category_record),
        )
        logger.info(
            "KG load completed — source=%s services_linked=%d categories_linked=%d",
            doc.url,
            result.services_linked,
            result.categories_linked,
        )
        return result


def _linked_count(record) -> int:
    if record is None:
        return 0
    return int(record["linked"])

