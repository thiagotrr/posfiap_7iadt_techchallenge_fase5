"""
knowledge/router.py

FastAPI APIRouter para health-check e status do Knowledge Graph.
Este router NÃO é registrado no app FastAPI aqui — responsabilidade do Dev 4.
Prefixo esperado: /api/v1/knowledge/
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from knowledge.graph_client import get_session
from knowledge.graph_schema import (
    NODE_ELEMENT_TYPE,
    NODE_STRIDE_CATEGORY,
    NODE_THREAT,
    NODE_MITIGATION,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["knowledge"])


@router.get("/knowledge/health")
def knowledge_health() -> JSONResponse:
    """
    Health-check do Knowledge Graph STRIDE.

    Returns:
        200 — KG acessível com contagem de nós.
        503 — Neo4j não está acessível.
    """
    try:
        with get_session() as session:
            counts = {}
            for label, key in [
                (NODE_ELEMENT_TYPE, "element_types"),
                (NODE_STRIDE_CATEGORY, "stride_categories"),
                (NODE_THREAT, "threats"),
                (NODE_MITIGATION, "mitigations"),
            ]:
                result = session.run(f"MATCH (n:{label}) RETURN count(n) AS cnt")
                counts[key] = result.single()["cnt"]

        kg_populated = (
            counts.get("element_types", 0) == 4
            and counts.get("stride_categories", 0) == 6
        )
        logger.info(
            "KG health check — kg_populated=%s element_types=%d stride_categories=%d",
            kg_populated,
            counts.get("element_types", 0),
            counts.get("stride_categories", 0),
        )
        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "kg_populated": kg_populated,
                "node_counts": counts,
            },
        )
    except Exception as exc:
        logger.error("KG health check failed — %s", exc)
        return JSONResponse(
            status_code=503,
            content={
                "status": "unavailable",
                "error": "Neo4j is not accessible. Check NEO4J_URI and credentials.",
                "detail": str(exc),
            },
        )
