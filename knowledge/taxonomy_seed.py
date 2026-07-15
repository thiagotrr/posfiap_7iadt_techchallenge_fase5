"""
knowledge/taxonomy_seed.py

Script de seed da taxonomia STRIDE determinística no Neo4j.

Popula:
  - 4 nós ElementType
  - 6 nós STRIDECategory
  - Matriz STRIDE-por-ElementType (relacionamentos SUSCETIVEL_A)
  - ≥ 2 Threat por categoria STRIDE (12 total)
  - ≥ 1 Mitigation por Threat
  - 11 nós CloudService do diagrama de referência + 1 External Entity genérico

Usa MERGE em todos os casos — idempotente por design.
Ameaças sourced da Microsoft Threat Modeling Tool:
  https://learn.microsoft.com/en-us/azure/security/develop/threat-modeling-tool-threats

Uso:
    python -m knowledge.taxonomy_seed
    # ou via scripts/seed_kg.py
"""

from __future__ import annotations
from knowledge.graph_client import get_session

import logging
import os

from neo4j import Driver

from knowledge.graph_schema import (
    NODE_ELEMENT_TYPE,
    NODE_STRIDE_CATEGORY,
    NODE_THREAT,
    NODE_MITIGATION,
    NODE_CLOUD_SERVICE,
    REL_SUSCETIVEL_A,
    REL_INCLUI_AMEACA,
    REL_MITIGADA_POR,
    REL_INSTANCIA_DE,
    STRIDE_MATRIX,
    REFERENCE_ARCHITECTURE_SERVICES,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dados da taxonomia STRIDE canônica
# ---------------------------------------------------------------------------

_ELEMENT_TYPES = [
    {"id": "process",         "name": "Process",         "description": "A process is a task that receives, modifies, or redirects data. Any application, service or function that transforms data."},
    {"id": "data_store",      "name": "Data Store",      "description": "A data store is a place where data is stored, such as a database, file system, message queue or cache."},
    {"id": "data_flow",       "name": "Data Flow",       "description": "A data flow represents the movement of data between processes, data stores, and external entities."},
    {"id": "external_entity", "name": "External Entity", "description": "An external entity is a person, organization, or external system that interacts with the system but is outside its trust boundary."},
]

_STRIDE_CATEGORIES = [
    {
        "id": "stride-s", "letter": "S", "name": "Spoofing",
        "description": (
            "Spoofing involves an attacker pretending to be someone or something else. "
            "This includes impersonating another user, process, or system to gain unauthorized access."
        ),
    },
    {
        "id": "stride-t", "letter": "T", "name": "Tampering",
        "description": (
            "Tampering involves the malicious modification of data. "
            "This includes unauthorized changes to persisted data, data in transit, or code."
        ),
    },
    {
        "id": "stride-r", "letter": "R", "name": "Repudiation",
        "description": (
            "Repudiation involves users or attackers denying that they performed an action. "
            "Systems without sufficient logging and auditing are vulnerable."
        ),
    },
    {
        "id": "stride-i", "letter": "I", "name": "InformationDisclosure",
        "description": (
            "Information Disclosure involves exposing information to individuals who are not supposed to have access to it. "
            "This includes exposing data in error messages, logs, backups, or through eavesdropping."
        ),
    },
    {
        "id": "stride-d", "letter": "D", "name": "DenialOfService",
        "description": (
            "Denial of Service involves denying valid users access to a service. "
            "Attackers can crash services, consume resources, or flood networks to prevent legitimate use."
        ),
    },
    {
        "id": "stride-e", "letter": "E", "name": "ElevationOfPrivilege",
        "description": (
            "Elevation of Privilege involves gaining capabilities beyond what is authorized. "
            "This includes exploiting bugs, misconfigurations, or design flaws to gain higher privileges."
        ),
    },
]

# Ameaças canônicas: ao menos 2 por categoria STRIDE
# Fonte: Microsoft Threat Modeling Tool threat categories
_THREATS = [
    # --- Spoofing ---
    {"id": "threat-s-001", "category_id": "stride-s",
     "name": "Identity Spoofing",
     "description": "An attacker pretends to be a legitimate user or service by forging identity credentials such as usernames, API keys, or tokens.",
     "severity": "high"},
    {"id": "threat-s-002", "category_id": "stride-s",
     "name": "Credential Theft and Replay",
     "description": "Attacker steals authentication tokens, session cookies, or API keys and replays them to impersonate a legitimate principal.",
     "severity": "critical"},

    # --- Tampering ---
    {"id": "threat-t-001", "category_id": "stride-t",
     "name": "Data Tampering in Transit",
     "description": "Attacker intercepts and alters data packets flowing between components, corrupting the integrity of information.",
     "severity": "high"},
    {"id": "threat-t-002", "category_id": "stride-t",
     "name": "Code and Configuration Injection",
     "description": "Attacker injects malicious input (SQL, XSS, command injection, template injection) that modifies the intended behavior of a process or data store.",
     "severity": "critical"},

    # --- Repudiation ---
    {"id": "threat-r-001", "category_id": "stride-r",
     "name": "Log Tampering or Deletion",
     "description": "Attacker modifies, corrupts, or deletes audit log entries to conceal evidence of malicious activity.",
     "severity": "high"},
    {"id": "threat-r-002", "category_id": "stride-r",
     "name": "Denial of Action",
     "description": "A user or process performs an action and later denies it because no cryptographic or audit evidence exists to prove authorship.",
     "severity": "medium"},

    # --- Information Disclosure ---
    {"id": "threat-i-001", "category_id": "stride-i",
     "name": "Sensitive Data Exposure",
     "description": "System exposes PII, credentials, internal architecture details, or secrets through error messages, verbose responses, or misconfigured permissions.",
     "severity": "high"},
    {"id": "threat-i-002", "category_id": "stride-i",
     "name": "Eavesdropping on Unencrypted Traffic",
     "description": "Attacker passively monitors unencrypted network traffic to capture credentials, session tokens, or sensitive business data.",
     "severity": "high"},

    # --- Denial of Service ---
    {"id": "threat-d-001", "category_id": "stride-d",
     "name": "Resource Exhaustion (Flood Attack)",
     "description": "Attacker sends a flood of requests or large payloads to exhaust CPU, memory, disk, or network bandwidth, making the service unavailable.",
     "severity": "high"},
    {"id": "threat-d-002", "category_id": "stride-d",
     "name": "Application-Level DoS (Algorithmic Complexity)",
     "description": "Attacker crafts inputs that trigger expensive algorithms (regex DoS, nested deserialization) causing the process to become unresponsive.",
     "severity": "medium"},

    # --- Elevation of Privilege ---
    {"id": "threat-e-001", "category_id": "stride-e",
     "name": "Privilege Escalation via Misconfigured IAM",
     "description": "Attacker exploits overly permissive IAM roles, missing resource policies, or confused deputy vulnerabilities to gain elevated access.",
     "severity": "critical"},
    {"id": "threat-e-002", "category_id": "stride-e",
     "name": "Insecure Deserialization for Code Execution",
     "description": "Attacker supplies malicious serialized objects that, when deserialized, execute arbitrary code with the privileges of the hosting process.",
     "severity": "critical"},
]

# Mitigações: ao menos 1 por Threat
_MITIGATIONS = [
    {"id": "mit-s-001", "threat_id": "threat-s-001",
     "name": "Multi-Factor Authentication (MFA)",
     "description": "Require MFA for all user and service accounts. Use hardware tokens or authenticator apps to prevent credential-only spoofing.",
     "control_type": "preventive"},
    {"id": "mit-s-002", "threat_id": "threat-s-002",
     "name": "Short-Lived Tokens and Token Revocation",
     "description": "Issue short-lived JWTs or session tokens; implement revocation lists and token rotation to limit the replay window.",
     "control_type": "preventive"},

    {"id": "mit-t-001", "threat_id": "threat-t-001",
     "name": "TLS 1.2+ for All Data in Transit",
     "description": "Enforce TLS 1.2 or higher on all service-to-service and client-to-service communication; disable legacy protocols (TLS 1.0/1.1, SSLv3).",
     "control_type": "preventive"},
    {"id": "mit-t-002", "threat_id": "threat-t-002",
     "name": "Input Validation, Parameterized Queries, and WAF",
     "description": "Validate and sanitize all user input; use parameterized queries / ORM; deploy AWS WAF with managed rule sets to block injection payloads.",
     "control_type": "preventive"},

    {"id": "mit-r-001", "threat_id": "threat-r-001",
     "name": "Immutable Audit Logging (CloudTrail + S3 Object Lock)",
     "description": "Write audit logs to CloudTrail and archive to S3 with Object Lock (WORM) enabled; alert on any CloudTrail logging disruption.",
     "control_type": "detective"},
    {"id": "mit-r-002", "threat_id": "threat-r-002",
     "name": "Digital Signatures and Non-Repudiation Keys",
     "description": "Sign critical API requests and data mutations using asymmetric keys managed by AWS KMS; store signed payloads as evidence.",
     "control_type": "preventive"},

    {"id": "mit-i-001", "threat_id": "threat-i-001",
     "name": "Data Minimization, Masking, and Least-Privilege Access",
     "description": "Return only required fields; mask PII and secrets in logs and responses; enforce RBAC/ABAC on all data access paths.",
     "control_type": "preventive"},
    {"id": "mit-i-002", "threat_id": "threat-i-002",
     "name": "End-to-End Encryption and Network Isolation",
     "description": "Encrypt all data flows with TLS; place sensitive services in private VPC subnets; use VPC endpoints to eliminate public internet exposure.",
     "control_type": "preventive"},

    {"id": "mit-d-001", "threat_id": "threat-d-001",
     "name": "AWS Shield + WAF Rate-Based Rules",
     "description": "Enable AWS Shield Standard (free) and create WAF rate-based rules to throttle abusive IPs; use CloudFront as a DDoS absorption layer.",
     "control_type": "preventive"},
    {"id": "mit-d-002", "threat_id": "threat-d-002",
     "name": "Input Size Limits, Timeouts, and Auto-Scaling",
     "description": "Enforce maximum payload size and request timeout at API Gateway; enable auto-scaling to absorb legitimate load spikes.",
     "control_type": "preventive"},

    {"id": "mit-e-001", "threat_id": "threat-e-001",
     "name": "Principle of Least Privilege with IAM Access Analyzer",
     "description": "Grant only the minimum permissions required; use IAM Access Analyzer to detect overly broad policies; enable SCPs in AWS Organizations.",
     "control_type": "preventive"},
    {"id": "mit-e-002", "threat_id": "threat-e-002",
     "name": "Disable Unsafe Deserialization and Use Allow-Lists",
     "description": "Avoid deserializing untrusted data in binary formats; prefer JSON with strict schema validation; use allow-list class filtering where deserialization is unavoidable.",
     "control_type": "preventive"},
]


# ---------------------------------------------------------------------------
# Seed function
# ---------------------------------------------------------------------------

def run_seed(driver: Driver) -> None:
    """
    Popula o Neo4j com a taxonomia STRIDE determinística.
    Idempotente: usa MERGE em todos os casos — pode ser executado múltiplas vezes.

    Args:
        driver: Driver Neo4j (neo4j.Driver).
    """
    logger.info("KG seed started")

    nodes_created = 0
    rels_created = 0

    with get_session()() as session:
        # ------------------------------------------------------------------
        # 1. Constraints de unicidade
        # ------------------------------------------------------------------
        _create_constraints(session)

        # ------------------------------------------------------------------
        # 2. Nós ElementType
        # ------------------------------------------------------------------
        for et in _ELEMENT_TYPES:
            result = session.run(
                f"""
                MERGE (n:{NODE_ELEMENT_TYPE} {{id: $id}})
                ON CREATE SET n.name = $name, n.description = $description
                ON MATCH  SET n.name = $name, n.description = $description
                RETURN n
                """,
                id=et["id"], name=et["name"], description=et["description"],
            )
            nodes_created += result.consume().counters.nodes_created

        # ------------------------------------------------------------------
        # 3. Nós STRIDECategory
        # ------------------------------------------------------------------
        for cat in _STRIDE_CATEGORIES:
            result = session.run(
                f"""
                MERGE (n:{NODE_STRIDE_CATEGORY} {{id: $id}})
                ON CREATE SET n.letter = $letter, n.name = $name, n.description = $description
                ON MATCH  SET n.letter = $letter, n.name = $name, n.description = $description
                RETURN n
                """,
                id=cat["id"], letter=cat["letter"],
                name=cat["name"], description=cat["description"],
            )
            nodes_created += result.consume().counters.nodes_created

        # ------------------------------------------------------------------
        # 4. Matriz STRIDE: relacionamentos SUSCETIVEL_A
        # ------------------------------------------------------------------
        letter_to_category_id = {cat["letter"]: cat["id"] for cat in _STRIDE_CATEGORIES}

        for element_type_id, letters in STRIDE_MATRIX.items():
            for letter in letters:
                cat_id = letter_to_category_id[letter]
                # severity baseada na categoria (convenção)
                severity = _default_severity_for_letter(letter)
                result = session.run(
                    f"""
                    MATCH (et:{NODE_ELEMENT_TYPE} {{id: $et_id}})
                    MATCH (sc:{NODE_STRIDE_CATEGORY} {{id: $sc_id}})
                    MERGE (et)-[r:{REL_SUSCETIVEL_A}]->(sc)
                    ON CREATE SET r.severity = $severity
                    ON MATCH  SET r.severity = $severity
                    RETURN r
                    """,
                    et_id=element_type_id, sc_id=cat_id, severity=severity,
                )
                rels_created += result.consume().counters.relationships_created

        # ------------------------------------------------------------------
        # 5. Nós Threat + relacionamentos INCLUI_AMEACA
        # ------------------------------------------------------------------
        for threat in _THREATS:
            result = session.run(
                f"""
                MERGE (t:{NODE_THREAT} {{id: $id}})
                ON CREATE SET t.name = $name, t.description = $description, t.severity = $severity
                ON MATCH  SET t.name = $name, t.description = $description, t.severity = $severity
                RETURN t
                """,
                id=threat["id"], name=threat["name"],
                description=threat["description"], severity=threat["severity"],
            )
            nodes_created += result.consume().counters.nodes_created

            result = session.run(
                f"""
                MATCH (sc:{NODE_STRIDE_CATEGORY} {{id: $cat_id}})
                MATCH (t:{NODE_THREAT} {{id: $threat_id}})
                MERGE (sc)-[r:{REL_INCLUI_AMEACA}]->(t)
                RETURN r
                """,
                cat_id=threat["category_id"], threat_id=threat["id"],
            )
            rels_created += result.consume().counters.relationships_created

        # ------------------------------------------------------------------
        # 6. Nós Mitigation + relacionamentos MITIGADA_POR
        # ------------------------------------------------------------------
        for mit in _MITIGATIONS:
            result = session.run(
                f"""
                MERGE (m:{NODE_MITIGATION} {{id: $id}})
                ON CREATE SET m.name = $name, m.description = $description, m.control_type = $control_type
                ON MATCH  SET m.name = $name, m.description = $description, m.control_type = $control_type
                RETURN m
                """,
                id=mit["id"], name=mit["name"],
                description=mit["description"], control_type=mit["control_type"],
            )
            nodes_created += result.consume().counters.nodes_created

            result = session.run(
                f"""
                MATCH (t:{NODE_THREAT} {{id: $threat_id}})
                MATCH (m:{NODE_MITIGATION} {{id: $mit_id}})
                MERGE (t)-[r:{REL_MITIGADA_POR}]->(m)
                RETURN r
                """,
                threat_id=mit["threat_id"], mit_id=mit["id"],
            )
            rels_created += result.consume().counters.relationships_created

        # ------------------------------------------------------------------
        # 7. Nós CloudService + relacionamentos INSTANCIA_DE
        # ------------------------------------------------------------------
        for svc in REFERENCE_ARCHITECTURE_SERVICES:
            svc_id = f"svc-{svc['name'].lower().replace(' ', '-')}"
            result = session.run(
                f"""
                MERGE (cs:{NODE_CLOUD_SERVICE} {{id: $id}})
                ON CREATE SET cs.name = $name, cs.provider = $provider,
                              cs.element_type = $element_type, cs.category = $category
                ON MATCH  SET cs.name = $name, cs.provider = $provider,
                              cs.element_type = $element_type, cs.category = $category
                RETURN cs
                """,
                id=svc_id, name=svc["name"], provider=svc["provider"],
                element_type=svc["element_type"], category=svc["category"],
            )
            nodes_created += result.consume().counters.nodes_created

            result = session.run(
                f"""
                MATCH (cs:{NODE_CLOUD_SERVICE} {{id: $svc_id}})
                MATCH (et:{NODE_ELEMENT_TYPE} {{id: $et_id}})
                MERGE (cs)-[r:{REL_INSTANCIA_DE}]->(et)
                RETURN r
                """,
                svc_id=svc_id, et_id=svc["element_type"],
            )
            rels_created += result.consume().counters.relationships_created

        # ------------------------------------------------------------------
        # 8. Nó genérico "External Entity"
        # ------------------------------------------------------------------
        result = session.run(
            f"""
            MERGE (cs:{NODE_CLOUD_SERVICE} {{id: 'svc-external-entity-generic'}})
            ON CREATE SET cs.name = 'External Entity',
                          cs.provider = 'generic',
                          cs.element_type = 'external_entity',
                          cs.category = 'external'
            ON MATCH  SET cs.name = 'External Entity',
                          cs.provider = 'generic',
                          cs.element_type = 'external_entity',
                          cs.category = 'external'
            RETURN cs
            """,
        )
        nodes_created += result.consume().counters.nodes_created

        result = session.run(
            f"""
            MATCH (cs:{NODE_CLOUD_SERVICE} {{id: 'svc-external-entity-generic'}})
            MATCH (et:{NODE_ELEMENT_TYPE} {{id: 'external_entity'}})
            MERGE (cs)-[r:{REL_INSTANCIA_DE}]->(et)
            RETURN r
            """,
        )
        rels_created += result.consume().counters.relationships_created

    logger.info(
        "KG seed completed — nodes_created=%d relationships_created=%d",
        nodes_created, rels_created,
    )


def _create_constraints(session) -> None:
    """Cria constraints de unicidade (idempotente via IF NOT EXISTS)."""
    labels = [
        NODE_ELEMENT_TYPE,
        NODE_STRIDE_CATEGORY,
        NODE_THREAT,
        NODE_MITIGATION,
        NODE_CLOUD_SERVICE,
        "Source",
    ]
    for label in labels:
        constraint_name = f"constraint_{label.lower()}_id_unique"
        session.run(
            f"""
            CREATE CONSTRAINT {constraint_name} IF NOT EXISTS
            FOR (n:{label}) REQUIRE n.id IS UNIQUE
            """
        )


def _default_severity_for_letter(letter: str) -> str:
    """Retorna severidade padrão do relacionamento SUSCETIVEL_A por letra STRIDE."""
    return {
        "S": "high",
        "T": "high",
        "R": "medium",
        "I": "high",
        "D": "high",
        "E": "critical",
    }.get(letter, "medium")


# ---------------------------------------------------------------------------
# Entrypoint CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    from knowledge.graph_client import get_driver

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    driver = get_driver()
    try:
        run_seed(driver)
    except Exception as exc:
        logger.error("Seed failed: %s", exc)
        sys.exit(1)
    finally:
        driver.close()
