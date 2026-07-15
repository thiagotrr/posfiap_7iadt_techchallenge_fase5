"""
knowledge/graph_client.py

Singleton de conexão Neo4j.
Lê NEO4J_URI, NEO4J_USER e NEO4J_PASSWORD de variáveis de ambiente.
O driver é encerrado automaticamente via atexit.
"""

from __future__ import annotations

import atexit
import logging
import os
from typing import Optional

from neo4j import GraphDatabase, Driver, Session

logger = logging.getLogger(__name__)

_driver: Optional[Driver] = None
_database: Optional[str]= None

def get_driver() -> Driver:
    """Retorna o driver Neo4j singleton, criando-o na primeira chamada."""
    global _driver
    if _driver is None:
        uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        user = os.environ.get("NEO4J_USER", "neo4j")
        password = os.environ.get("NEO4J_PASSWORD", "")
        _database = os.environ.get("NEO4J_DATABASE", "neo4j")
        if not password:
            raise RuntimeError(
                "NEO4J_PASSWORD environment variable is required but not set."
            )
        _driver = GraphDatabase.driver(uri, auth=(user, password))
        logger.info("Neo4j driver initialized — uri=%s user=%s", uri, user)
        atexit.register(_close_driver)
    return _driver

def get_session() -> Session:
    """Retorna uma sessão apontado para NEO4J_DATABASE. Utilizar esta invés de driver.session()."""
    return get_driver().session(database=_database or "neo4j")

def _close_driver() -> None:
    global _driver
    if _driver is not None:
        _driver.close()
        logger.info("Neo4j driver closed.")
        _driver = None
