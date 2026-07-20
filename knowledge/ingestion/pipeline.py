"""Orquestrador condicional do pipeline de ingestão do Knowledge Graph."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Literal

from neo4j import Driver

from knowledge.crawler.storage import CrawlStorage, MANIFEST_FILENAME
from knowledge.graph_client import get_driver
from knowledge.graph_schema import NODE_SOURCE
from knowledge.ingestion.classifier import STRIDEClassifier
from knowledge.ingestion.loader import KGLoader
from knowledge.taxonomy_seed import run_seed

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    status: Literal["skipped", "completed", "partial"]
    documents_processed: int
    documents_failed: int
    elapsed_seconds: float


def run_ingestion(driver: Driver | None = None, force: bool = False) -> IngestionResult:
    """Executa seed e enriquecimento somente quando necessário."""
    started_at = time.monotonic()
    active_driver = driver or get_driver()
    storage = CrawlStorage()
    manifest_path = storage.output_dir / MANIFEST_FILENAME

    if not force and _kg_has_complete_seed(active_driver):
        if not manifest_path.exists() or _kg_has_enrichment(active_driver):
            logger.info("KG already populated — skipping ingestion")
            return IngestionResult(
                status="skipped",
                documents_processed=0,
                documents_failed=0,
                elapsed_seconds=time.monotonic() - started_at,
            )
        logger.info(
            "KG seed complete — enrichment pending for manifest at %s",
            manifest_path,
        )
    elif not _kg_has_complete_seed(active_driver) or force:
        run_seed(active_driver)

    if not manifest_path.exists():
        result = IngestionResult(
            status="completed",
            documents_processed=0,
            documents_failed=0,
            elapsed_seconds=time.monotonic() - started_at,
        )
        _log_completion(result)
        return result

    documents = storage.load_all()
    logger.info("Ingestion started — documents_total=%d", len(documents))
    classifier = STRIDEClassifier()
    loader = KGLoader()
    processed = 0
    failed = 0

    for index, doc in enumerate(documents, start=1):
        try:
            classification = classifier.classify(doc)
            loader.load(doc, classification, active_driver)
            processed += 1
        except Exception as exc:
            failed += 1
            logger.warning(
                "Ingestion document failed — url=%s error=%s",
                doc.url,
                type(exc).__name__,
            )
        logger.info(
            "Ingestion progress: %d/%d documents processed",
            index,
            len(documents),
        )

    result = IngestionResult(
        status="partial" if failed else "completed",
        documents_processed=processed,
        documents_failed=failed,
        elapsed_seconds=time.monotonic() - started_at,
    )
    _log_completion(result)
    return result


def _kg_has_complete_seed(driver: Driver) -> bool:
    with driver.session() as session:
        record = session.run(
            """
            MATCH (element:ElementType)
            WITH count(element) AS element_types
            MATCH (category:STRIDECategory)
            RETURN element_types, count(category) AS stride_categories
            """
        ).single()
    return bool(
        record
        and record["element_types"] == 4
        and record["stride_categories"] == 6
    )


def _kg_has_enrichment(driver: Driver) -> bool:
    with driver.session() as session:
        record = session.run(
            f"MATCH (source:{NODE_SOURCE}) RETURN count(source) AS sources"
        ).single()
    return bool(record and record["sources"] > 0)


def _log_completion(result: IngestionResult) -> None:
    logger.info(
        "Ingestion completed — status=%s processed=%d failed=%d elapsed=%.2fs",
        result.status,
        result.documents_processed,
        result.documents_failed,
        result.elapsed_seconds,
    )
