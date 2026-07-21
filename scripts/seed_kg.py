"""
scripts/seed_kg.py

Executa o seed da taxonomia STRIDE no Neo4j.

Uso:
    python scripts/seed_kg.py

Variáveis de ambiente obrigatórias:
    NEO4J_URI       — URI do Neo4j (default: bolt://localhost:7687)
    NEO4J_USER      — Usuário Neo4j (default: neo4j)
    NEO4J_PASSWORD  — Senha Neo4j (obrigatória)

Também pode ser executado como módulo:
    python -m knowledge.taxonomy_seed
"""

import logging
import sys
import os
from dotenv import load_dotenv

# Garante que a raiz do projeto está no path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

from knowledge.graph_client import get_driver
from knowledge.taxonomy_seed import run_seed

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Starting KG seed via scripts/seed_kg.py")
    try:
        run_seed()
        logger.info("Seed completed successfully.")
    except Exception as exc:
        logger.error("Seed failed: %s", exc)
        sys.exit(1)
    finally:
        pass # Driver é fechado automaticamente pelo singleton com o uso de `with get_session() as session:`
        
