"""Executa o pipeline condicional de ingestão do Knowledge Graph."""

import argparse
import logging
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from knowledge.ingestion.pipeline import run_ingestion


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingere o corpus crawleado no Neo4j.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Executa seed e ingestão mesmo quando o KG já está populado.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )
    result = run_ingestion(force=args.force)
    print(
        f"status={result.status} processed={result.documents_processed} "
        f"failed={result.documents_failed} elapsed={result.elapsed_seconds:.2f}s"
    )
    return 0 if result.status != "partial" else 1


if __name__ == "__main__":
    raise SystemExit(main())

