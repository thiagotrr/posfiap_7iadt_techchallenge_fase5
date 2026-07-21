"""
scripts/run_dev2_pipeline.py

Script consolidado fim-a-fim do fluxo Dev 2 (Knowledge Graph).

Orquestra:
  1. Verificação de pré-requisitos (Neo4j, variáveis de ambiente)
  2. Subida do Neo4j via Docker Compose (se necessário)
  3. Crawler completo OU corpus de amostra (--sample-corpus)
  4. Ingestão condicional no Neo4j (seed + classificação + loader)
  5. Validação com queries Cypher canônicas

Uso:
    # Pipeline completo (crawler real + ingestão + validação)
    python scripts/run_dev2_pipeline.py

    # Corpus mínimo para dev/teste (sem internet)
    python scripts/run_dev2_pipeline.py --sample-corpus

    # Pular crawl (usar corpus existente em data/crawled/)
    python scripts/run_dev2_pipeline.py --skip-crawl

    # Forçar re-ingestão mesmo com KG já populado
    python scripts/run_dev2_pipeline.py --force

    # Apenas validação (Neo4j já populado)
    python scripts/run_dev2_pipeline.py --validate-only

Variáveis de ambiente (ver .env.example):
    NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD  — conexão Neo4j (obrigatórias)
    KG_CLASSIFIER_LLM_PROVIDER, OPENAI_API_KEY / GOOGLE_API_KEY — classificador LLM
    KG_CRAWL_SSL_VERIFY=false                — workaround SSL no Windows dev
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# Garante imports a partir da raiz do projeto
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------

def _run_step(label: str, fn) -> bool:
    """Executa um passo do pipeline com log e tratamento de erro."""
    print(f"\n{'-' * 60}")
    print(f"  PASSO: {label}")
    print("-" * 60)
    try:
        fn()
        print(f"  [OK] {label} -- concluido")
        return True
    except subprocess.CalledProcessError as exc:
        print(f"  [FAIL] {label} -- falhou (exit {exc.returncode})")
        return False
    except Exception as exc:
        print(f"  [FAIL] {label} -- erro: {exc}")
        return False


def _python(*args: str) -> None:
    """Executa um script Python usando o mesmo interpretador."""
    cmd = [sys.executable, *args]
    logger.info("Executando: %s", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=ROOT)


def _docker_compose(*args: str) -> None:
    cmd = ["docker", "compose", *args]
    logger.info("Executando: %s", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=ROOT)


# ---------------------------------------------------------------------------
# Passos do pipeline
# ---------------------------------------------------------------------------

def check_prerequisites() -> None:
    """Verifica variáveis de ambiente e conectividade Neo4j."""
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        raise RuntimeError(
            "NEO4J_PASSWORD não definida. Copie .env.example → .env e configure."
        )

    # Ao rodar do host, URI deve apontar para localhost (não o nome do container)
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    if "neo4j:" in uri and "localhost" not in uri:
        logger.warning(
            "NEO4J_URI=%s parece ser a URI interna do Docker. "
            "Do host, use bolt://localhost:7687",
            uri,
        )
        os.environ["NEO4J_URI"] = "bolt://localhost:7687"

    from knowledge.graph_client import get_driver

    driver = get_driver()
    for attempt in range(1, 6):
        try:
            driver.verify_connectivity()
            print(f"  Neo4j acessível em {os.environ['NEO4J_URI']}")
            return
        except Exception:
            if attempt == 5:
                raise RuntimeError(
                    "Neo4j indisponível após 5 tentativas. "
                    "Execute: docker compose up -d neo4j"
                )
            print(f"  Aguardando Neo4j... tentativa {attempt}/5")
            time.sleep(5)


def ensure_neo4j_running() -> None:
    """Sobe o container Neo4j se não estiver healthy."""
    result = subprocess.run(
        ["docker", "compose", "ps", "--status=running", "neo4j"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    if "neo4j" in result.stdout:
        print("  Container neo4j já está em execução")
        return

    print("  Subindo Neo4j via docker compose...")
    _docker_compose("up", "-d", "neo4j")

    # Aguarda healthcheck
    for attempt in range(1, 13):
        health = subprocess.run(
            ["docker", "compose", "ps", "neo4j"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        if "healthy" in health.stdout:
            print("  Neo4j healthy")
            return
        print(f"  Aguardando healthcheck... {attempt}/12")
        time.sleep(5)

    raise RuntimeError("Neo4j não ficou healthy a tempo")


def run_crawler() -> None:
    """Executa o crawler completo (Épico 2)."""
    _python("scripts/run_crawler.py")


def run_sample_corpus() -> None:
    """Copia corpus mínimo versionado (sem internet)."""
    _python("scripts/bootstrap_sample_corpus.py")


def run_ingestion(force: bool) -> None:
    """Executa pipeline de ingestão (Épico 3)."""
    args = ["scripts/run_ingestion.py"]
    if force:
        args.append("--force")
    _python(*args)


def run_validation(graph_sample: int, export_path: str | None) -> None:
    """Executa queries Cypher de validação."""
    args = ["scripts/validate_kg.py", "--graph-sample", str(graph_sample)]
    if export_path:
        args.extend(["--export", export_path])
    _python(*args)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pipeline fim-a-fim Dev 2 — Knowledge Graph STRIDE",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--sample-corpus",
        action="store_true",
        help="Usa corpus mínimo versionado (3 docs) em vez do crawler real",
    )
    parser.add_argument(
        "--skip-crawl",
        action="store_true",
        help="Pula crawl — usa corpus existente em data/crawled/",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Força re-seed e re-ingestão mesmo com KG já populado",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Apenas executa validação Cypher (Neo4j deve estar populado)",
    )
    parser.add_argument(
        "--skip-neo4j-start",
        action="store_true",
        help="Não tenta subir Neo4j via docker compose",
    )
    parser.add_argument(
        "--graph-sample",
        type=int,
        default=15,
        help="Número de relações de enriquecimento na validação (default: 15)",
    )
    parser.add_argument(
        "--export-graph",
        metavar="PATH",
        help="Exporta amostra da taxonomia em JSON durante validação",
    )
    args = parser.parse_args()

    os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
    os.environ.setdefault("NEO4J_USER", "neo4j")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    print("\n" + "=" * 60)
    print("  Dev 2 Pipeline — Knowledge Graph STRIDE")
    print("=" * 60)

    steps_ok = True

    if args.validate_only:
        steps_ok &= _run_step(
            "Validação Cypher",
            lambda: run_validation(args.graph_sample, args.export_graph),
        )
    else:
        if not args.skip_neo4j_start:
            steps_ok &= _run_step("Neo4j (Docker Compose)", ensure_neo4j_running)

        steps_ok &= _run_step("Pré-requisitos", check_prerequisites)

        if not args.skip_crawl:
            if args.sample_corpus:
                steps_ok &= _run_step("Corpus de amostra", run_sample_corpus)
            else:
                steps_ok &= _run_step("Crawler completo (Épico 2)", run_crawler)
        else:
            print("\n  (Crawl ignorado — usando corpus em data/crawled/)")

        if steps_ok:
            steps_ok &= _run_step(
                "Ingestão (Épico 3)",
                lambda: run_ingestion(args.force),
            )

        if steps_ok:
            steps_ok &= _run_step(
                "Validação Cypher",
                lambda: run_validation(args.graph_sample, args.export_graph),
            )

    print("\n" + "=" * 60)
    if steps_ok:
        print("  Pipeline Dev 2 concluído com sucesso.")
        print("  Neo4j Browser: http://localhost:7474")
        print("=" * 60)
        return 0

    print("  Pipeline Dev 2 concluído com ERROS — verifique os logs acima.")
    print("=" * 60)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
