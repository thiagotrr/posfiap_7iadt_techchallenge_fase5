"""API pública do pipeline de ingestão do Knowledge Graph."""

from knowledge.ingestion.classifier import ClassificationResult, STRIDEClassifier
from knowledge.ingestion.loader import KGLoader, LoadResult
from knowledge.ingestion.pipeline import IngestionResult, run_ingestion

__all__ = [
    "ClassificationResult",
    "IngestionResult",
    "KGLoader",
    "LoadResult",
    "STRIDEClassifier",
    "run_ingestion",
]
