"""
scripts/migrate_kg_relationships_pt_br.py

Renomeia tipos de relacionamento en_US para pt_BR no Neo4j.

Mapeamento aplicado:
    COVERS_SERVICE            -> COBRE_SERVICO
    COVERS_CATEGORY           -> COBRE_CATEGORIA
    HAS_SPECIFIC_THREAT       -> POSSUI_AMEACA_ESPECIFICA
    HAS_SPECIFIC_MITIGATION   -> POSSUI_MITIGACAO_ESPECIFICA

Uso:
    python scripts/migrate_kg_relationships_pt_br.py
    python scripts/migrate_kg_relationships_pt_br.py --dry-run

Variáveis de ambiente obrigatórias:
    NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from knowledge.graph_client import get_driver
from knowledge.graph_schema import (
    REL_COBRE_CATEGORIA,
    REL_COBRE_SERVICO,
    REL_COVERS_CATEGORY,
    REL_COVERS_SERVICE,
    REL_HAS_SPECIFIC_MITIGATION,
    REL_HAS_SPECIFIC_THREAT,
    REL_POSSUI_AMEACA_ESPECIFICA,
    REL_POSSUI_MITIGACAO_ESPECIFICA,
)

logger = logging.getLogger(__name__)

RELATIONSHIP_RENAMES: dict[str, str] = {
    REL_COVERS_SERVICE: REL_COBRE_SERVICO,
    REL_COVERS_CATEGORY: REL_COBRE_CATEGORIA,
    REL_HAS_SPECIFIC_THREAT: REL_POSSUI_AMEACA_ESPECIFICA,
    REL_HAS_SPECIFIC_MITIGATION: REL_POSSUI_MITIGACAO_ESPECIFICA,
}


def _count_relationships(session, rel_type: str) -> int:
    result = session.run(
        f"MATCH ()-[r:{rel_type}]->() RETURN count(r) AS total"
    )
    record = result.single()
    return int(record["total"]) if record else 0


def _rename_relationship_type(
    session,
    old_type: str,
    new_type: str,
    *,
    dry_run: bool,
) -> int:
    existing = _count_relationships(session, old_type)
    if existing == 0:
        logger.info("  %s: nenhum relacionamento encontrado — ignorado", old_type)
        return 0

    if dry_run:
        logger.info("  %s -> %s: %d relacionamento(s) seriam renomeados", old_type, new_type, existing)
        return existing

    result = session.run(
        f"""
        MATCH (a)-[r:{old_type}]->(b)
        WITH a, b, r, properties(r) AS props
        CREATE (a)-[new:{new_type}]->(b)
        SET new = props
        DELETE r
        RETURN count(new) AS renamed
        """
    )
    record = result.single()
    renamed = int(record["renamed"]) if record else 0
    logger.info("  %s -> %s: %d relacionamento(s) renomeado(s)", old_type, new_type, renamed)
    return renamed


def migrate(*, dry_run: bool = False) -> dict[str, int]:
    """Renomeia relacionamentos en_US para pt_BR no Neo4j."""
    driver = get_driver()
    driver.verify_connectivity()

    totals: dict[str, int] = {}
    with driver.session() as session:
        for old_type, new_type in RELATIONSHIP_RENAMES.items():
            totals[old_type] = _rename_relationship_type(
                session,
                old_type,
                new_type,
                dry_run=dry_run,
            )

    return totals


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migra tipos de relacionamento en_US para pt_BR no Neo4j."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Apenas reporta quantos relacionamentos seriam renomeados",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    mode = "dry-run" if args.dry_run else "execução"
    logger.info("Iniciando migração semântica de relacionamentos (%s)", mode)

    try:
        totals = migrate(dry_run=args.dry_run)
    except Exception as exc:
        logger.error("Migração falhou: %s", exc)
        return 1

    total_renamed = sum(totals.values())
    logger.info(
        "Migração concluída — %d relacionamento(s) %s",
        total_renamed,
        "identificados" if args.dry_run else "renomeados",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
