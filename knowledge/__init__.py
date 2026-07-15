"""
knowledge — Base de Conhecimento STRIDE (Knowledge Graph Neo4j)

Exporta os contratos públicos consumidos pelo Dev 3 (LangGraph) e Dev 4 (FastAPI).
"""

from knowledge.models import KGQueryResult, ThreatResult, MitigationResult, STRIDEResult
from knowledge.query import get_stride_threats
from knowledge.ingestion.pipeline import run_ingestion

__all__ = [
    "get_stride_threats",
    "run_ingestion",
    "KGQueryResult",
    "ThreatResult",
    "MitigationResult",
    "STRIDEResult",
]
