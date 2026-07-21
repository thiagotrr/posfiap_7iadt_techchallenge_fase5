"""
scripts/validate_kg.py

Executa queries Cypher de validação no Neo4j e exibe resumos do grafo.

Uso:
    python scripts/validate_kg.py
    python scripts/validate_kg.py --graph-sample 30

Variáveis de ambiente obrigatórias:
    NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from knowledge.graph_client import get_driver


def _run_query(session, cypher: str, params: dict | None = None) -> list[dict]:
    result = session.run(cypher, params or {})
    return [dict(record) for record in result]


def print_section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


def validate_health(session) -> None:
    """Query 4 — health-check de contagem de nós da taxonomia base."""
    print_section("Query 4 — Health-check (taxonomia base)")
    rows = _run_query(
        session,
        """
        MATCH (et:ElementType) WITH count(et) AS element_types
        MATCH (sc:STRIDECategory) WITH element_types, count(sc) AS stride_categories
        MATCH (t:Threat) WITH element_types, stride_categories, count(t) AS threats
        MATCH (m:Mitigation) WITH element_types, stride_categories, threats, count(m) AS mitigations
        RETURN element_types, stride_categories, threats, mitigations
        """,
    )
    row = rows[0]
    print(
        f"  ElementTypes={row['element_types']}  "
        f"STRIDECategories={row['stride_categories']}  "
        f"Threats={row['threats']}  Mitigations={row['mitigations']}"
    )
    expected = (4, 6, 12, 12)
    actual = (
        row["element_types"],
        row["stride_categories"],
        row["threats"],
        row["mitigations"],
    )
    status = "OK" if actual == expected else "ATENÇÃO (valores inesperados pós-seed)"
    print(f"  Esperado pós-seed: {expected} — Status: {status}")


def validate_node_counts(session) -> None:
    print_section("Contagem de nós por label")
    rows = _run_query(
        session,
        "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS total ORDER BY label",
    )
    for row in rows:
        print(f"  {row['label']:20s} {row['total']:>5}")


def validate_stride_categories(session, element_type: str = "data_store") -> None:
    """Query 1 — categorias STRIDE por ElementType."""
    print_section(f"Query 1 — STRIDE para ElementType '{element_type}'")
    rows = _run_query(
        session,
        """
        MATCH (et:ElementType {id: $element_type})
              -[:SUSCETIVEL_A]->(sc:STRIDECategory)
        RETURN sc.letter AS letter, sc.name AS name
        ORDER BY sc.letter
        """,
        {"element_type": element_type},
    )
    for row in rows:
        print(f"  [{row['letter']}] {row['name']}")


def validate_taxonomy_threats(session, element_type: str = "data_store") -> None:
    """Query 2 — ameaças e mitigações (amostra)."""
    print_section(f"Query 2 — Ameaças e mitigações para '{element_type}' (top 8)")
    rows = _run_query(
        session,
        """
        MATCH (et:ElementType {id: $element_type})
              -[:SUSCETIVEL_A]->(sc:STRIDECategory)
              -[:INCLUI_AMEACA]->(t:Threat)
              -[:MITIGADA_POR]->(m:Mitigation)
        RETURN sc.letter AS category,
               t.name AS threat,
               t.severity AS severity,
               m.name AS mitigation
        ORDER BY sc.letter, t.severity DESC
        LIMIT 8
        """,
        {"element_type": element_type},
    )
    for row in rows:
        print(
            f"  [{row['category']}] {row['threat']} ({row['severity']}) "
            f"-> {row['mitigation']}"
        )


def validate_enrichment(session) -> None:
    """Validação pós-ingestão — nós Source e vínculos de enriquecimento."""
    print_section("Enriquecimento pós-ingestão")
    rows = _run_query(
        session,
        """
        MATCH (source:Source)
        OPTIONAL MATCH (source)-[:COVERS_SERVICE]->(cs:CloudService)
        OPTIONAL MATCH (source)-[:COVERS_CATEGORY]->(sc:STRIDECategory)
        RETURN count(DISTINCT source) AS sources,
               count(DISTINCT cs) AS services_covered,
               count(DISTINCT sc) AS categories_covered
        """,
    )
    row = rows[0]
    print(f"  Sources           : {row['sources']}")
    print(f"  Serviços cobertos : {row['services_covered']}")
    print(f"  Categorias cobertas: {row['categories_covered']}")

    rows = _run_query(
        session,
        """
        MATCH (source:Source)-[:COVERS_SERVICE]->(cs:CloudService)
        RETURN cs.name AS service, count(source) AS doc_count
        ORDER BY doc_count DESC
        LIMIT 10
        """,
    )
    if rows:
        print("\n  Top serviços por documentos:")
        for row in rows:
            print(f"    {row['service']:30s} {row['doc_count']:>3} docs")


def validate_graph_sample(session, limit: int) -> None:
    """Amostra de subgrafo para visualização no Neo4j Browser."""
    print_section(f"Amostra de subgrafo (até {limit} nós)")
    rows = _run_query(
        session,
        """
        MATCH (source:Source)-[:COVERS_SERVICE]->(cs:CloudService)
              -[:INSTANCIA_DE]->(et:ElementType)
              -[:SUSCETIVEL_A]->(sc:STRIDECategory)
        RETURN source.title AS source_title,
               cs.name AS cloud_service,
               et.id AS element_type,
               sc.letter AS stride_letter
        LIMIT $limit
        """,
        {"limit": limit},
    )
    if not rows:
        print("  (Nenhum enriquecimento encontrado — execute a ingestão após o crawl)")
        return
    for row in rows:
        print(
            f"  Source: {row['source_title'][:50]}…"
            if len(row["source_title"]) > 50
            else f"  Source: {row['source_title']}"
        )
        print(
            f"    -> {row['cloud_service']} ({row['element_type']}) "
            f"STRIDE [{row['stride_letter']}]"
        )

    print("\n  Cypher para visualizar no Neo4j Browser (http://localhost:7474):")
    print(
        """
  MATCH (source:Source)-[:COVERS_SERVICE]->(cs:CloudService)
        -[:INSTANCIA_DE]->(et:ElementType)
        -[:SUSCETIVEL_A]->(sc:STRIDECategory)
  RETURN source, cs, et, sc LIMIT 25
    """.strip()
    )


def export_graph_json(session, output_path: str) -> None:
    """Exporta amostra do grafo em JSON para inspeção."""
    rows = _run_query(
        session,
        """
        MATCH (et:ElementType)-[:SUSCETIVEL_A]->(sc:STRIDECategory)
              -[:INCLUI_AMEACA]->(t:Threat)-[:MITIGADA_POR]->(m:Mitigation)
        RETURN et.id AS element_type, sc.letter AS category,
               t.name AS threat, m.name AS mitigation
        ORDER BY et.id, sc.letter
        LIMIT 100
        """,
    )
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=2)
    print(f"\n  Grafo exportado para: {output_path} ({len(rows)} registros)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida o Knowledge Graph Neo4j.")
    parser.add_argument(
        "--graph-sample",
        type=int,
        default=15,
        help="Número de relações de enriquecimento a exibir (default: 15)",
    )
    parser.add_argument(
        "--export",
        metavar="PATH",
        help="Exporta amostra da taxonomia em JSON",
    )
    args = parser.parse_args()

    os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")

    driver = get_driver()
    try:
        driver.verify_connectivity()
    except Exception as exc:
        print(f"ERRO: Neo4j indisponível — {exc}")
        print("  Verifique: docker compose up -d neo4j")
        return 1

    with driver.session() as session:
        validate_health(session)
        validate_node_counts(session)
        validate_stride_categories(session, "data_store")
        validate_taxonomy_threats(session, "process")
        validate_enrichment(session)
        validate_graph_sample(session, args.graph_sample)
        if args.export:
            export_graph_json(session, args.export)

    print("\nValidação concluída.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
