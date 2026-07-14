"""
knowledge/ingestion/pipeline.py — STUB do Épico 1

Implementação completa entregue no Épico 3 (US-3.3).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal, Optional

from neo4j import Driver

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    status: Literal["skipped", "completed", "partial"]
    documents_processed: int
    documents_failed: int
    elapsed_seconds: float


def run_ingestion(driver: Optional[Driver] = None, force: bool = False) -> IngestionResult:
    """
    Orquestrador de ingestão condicional.
    Stub do Épico 1 — implementação completa no Épico 3.
    """
    logger.warning("run_ingestion() stub called — full implementation in Épico 3.")
    raise NotImplementedError(
        "run_ingestion() full implementation is delivered in Épico 3 (US-3.3)."
    )
