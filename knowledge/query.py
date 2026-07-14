"""
knowledge/query.py

Interface pública de query ao Knowledge Graph STRIDE.

Implementação completa entregue no Épico 4 (US-4.1).
No Épico 1 esta função é um stub que permite Dev 3 e Dev 4 mockarem
usando knowledge.fixtures enquanto a implementação real não existe.
"""

from __future__ import annotations

import logging
from typing import Optional

from neo4j import Driver

from knowledge.models import KGQueryResult
from knowledge.exceptions import ElementTypeNotFoundError

logger = logging.getLogger(__name__)


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
    # --- Stub do Épico 1 — substituído pela implementação real no Épico 4 ---
    logger.warning(
        "KG query — get_stride_threats() stub called — "
        "element_type=%s service=%s (not yet implemented; use fixtures)",
        element_type,
        cloud_service,
    )
    raise NotImplementedError(
        "get_stride_threats() full implementation is delivered in Épico 4 (US-4.1). "
        "For Semana 1, use knowledge.fixtures to mock this function."
    )
