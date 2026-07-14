"""
knowledge/fixtures.py

Fixtures de KGQueryResult para cada element_type.
Usadas por Dev 3 (LangGraph) e Dev 4 (FastAPI/Streamlit) para mockar
get_stride_threats() durante a Semana 1, antes do Neo4j estar integrado.

Baseadas na taxonomia STRIDE canônica Microsoft.
Fonte: https://learn.microsoft.com/en-us/azure/security/develop/threat-modeling-tool-threats
"""

from __future__ import annotations

from knowledge.models import KGQueryResult, STRIDEResult, ThreatResult, MitigationResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _t(id: str, name: str, description: str, severity: str) -> ThreatResult:
    return ThreatResult(id=id, name=name, description=description, severity=severity)  # type: ignore[arg-type]


def _m(id: str, name: str, description: str, control_type: str) -> MitigationResult:
    return MitigationResult(id=id, name=name, description=description, control_type=control_type)  # type: ignore[arg-type]


def _r(category: str, letter: str, threats: list, mitigations: list) -> STRIDEResult:
    return STRIDEResult(category=category, letter=letter, threats=threats, mitigations=mitigations)


# ---------------------------------------------------------------------------
# Fixture: process
# Categorias aplicáveis: S, T, R, I, D, E (todas)
# ---------------------------------------------------------------------------

FIXTURE_PROCESS = KGQueryResult(
    element_type="process",
    cloud_service=None,
    query_source="taxonomy",
    stride_results=[
        _r("Spoofing", "S", [
            _t("threat-s-001", "Identity Spoofing",
               "An attacker impersonates another user or service to gain unauthorized access.",
               "high"),
            _t("threat-s-002", "Credential Theft",
               "Attacker steals authentication credentials (tokens, passwords) to masquerade as a legitimate process.",
               "critical"),
        ], [
            _m("mit-s-001", "Multi-Factor Authentication",
               "Require MFA for all user and service accounts accessing the process.",
               "preventive"),
            _m("mit-s-002", "Mutual TLS (mTLS)",
               "Use certificate-based mutual authentication between services.",
               "preventive"),
        ]),
        _r("Tampering", "T", [
            _t("threat-t-001", "Data Tampering in Transit",
               "Attacker intercepts and modifies data while it is being transmitted to the process.",
               "high"),
            _t("threat-t-002", "Code Injection",
               "Attacker injects malicious code (SQL, XSS, command injection) into the process input.",
               "critical"),
        ], [
            _m("mit-t-001", "Transport Layer Security (TLS 1.2+)",
               "Encrypt all data in transit using TLS to prevent interception and modification.",
               "preventive"),
            _m("mit-t-002", "Input Validation and Sanitization",
               "Validate and sanitize all input before processing to prevent injection attacks.",
               "preventive"),
        ]),
        _r("Repudiation", "R", [
            _t("threat-r-001", "Log Tampering",
               "Attacker modifies or deletes audit logs to erase evidence of malicious actions.",
               "high"),
            _t("threat-r-002", "Denial of Action",
               "User or service denies having performed an action due to insufficient audit trail.",
               "medium"),
        ], [
            _m("mit-r-001", "Immutable Audit Logging",
               "Write audit logs to an append-only, tamper-evident store (e.g., CloudTrail, CloudWatch Logs).",
               "detective"),
            _m("mit-r-002", "Digital Signatures",
               "Sign critical operations with a non-repudiation key to prove authorship.",
               "preventive"),
        ]),
        _r("InformationDisclosure", "I", [
            _t("threat-i-001", "Sensitive Data Exposure",
               "Process exposes sensitive data (PII, credentials, internal state) in error messages or responses.",
               "high"),
            _t("threat-i-002", "Insecure Direct Object Reference",
               "Attacker accesses data belonging to another user by manipulating resource identifiers.",
               "high"),
        ], [
            _m("mit-i-001", "Data Masking and Minimization",
               "Return only the minimum necessary data; mask sensitive fields in logs and responses.",
               "preventive"),
            _m("mit-i-002", "Authorization Checks (RBAC/ABAC)",
               "Enforce fine-grained authorization on every resource access.",
               "preventive"),
        ]),
        _r("DenialOfService", "D", [
            _t("threat-d-001", "Resource Exhaustion",
               "Attacker floods the process with requests, exhausting CPU, memory or connections.",
               "high"),
            _t("threat-d-002", "Application-Level DoS",
               "Attacker crafts expensive queries or payloads that cause the process to timeout or crash.",
               "medium"),
        ], [
            _m("mit-d-001", "Rate Limiting and Throttling",
               "Implement request rate limits and throttling at the API Gateway or load balancer layer.",
               "preventive"),
            _m("mit-d-002", "Auto-scaling and Circuit Breakers",
               "Use auto-scaling policies and circuit-breaker patterns to maintain availability under load.",
               "corrective"),
        ]),
        _r("ElevationOfPrivilege", "E", [
            _t("threat-e-001", "Privilege Escalation via Misconfiguration",
               "Attacker exploits overly permissive IAM policies or process configurations to gain elevated access.",
               "critical"),
            _t("threat-e-002", "Insecure Deserialization",
               "Attacker crafts malicious serialized objects that execute arbitrary code with elevated privileges.",
               "critical"),
        ], [
            _m("mit-e-001", "Principle of Least Privilege",
               "Assign the minimum permissions required for each process; use IAM roles with explicit deny.",
               "preventive"),
            _m("mit-e-002", "Secure Deserialization",
               "Avoid deserializing untrusted data; use safe serialization formats (JSON) over binary formats.",
               "preventive"),
        ]),
    ],
    total_threats=12,
)

# ---------------------------------------------------------------------------
# Fixture: data_store
# Categorias aplicáveis: T, R, I, D
# ---------------------------------------------------------------------------

FIXTURE_DATA_STORE = KGQueryResult(
    element_type="data_store",
    cloud_service=None,
    query_source="taxonomy",
    stride_results=[
        _r("Tampering", "T", [
            _t("threat-ds-t-001", "Unauthorized Data Modification",
               "Attacker with unauthorized write access modifies records in the data store.",
               "critical"),
            _t("threat-ds-t-002", "SQL/NoSQL Injection",
               "Attacker injects malicious query payloads to manipulate or exfiltrate stored data.",
               "critical"),
        ], [
            _m("mit-ds-t-001", "Encryption at Rest",
               "Encrypt all data at rest using managed keys (AWS KMS, Azure Key Vault).",
               "preventive"),
            _m("mit-ds-t-002", "Parameterized Queries / ORM",
               "Use parameterized queries or ORM frameworks to prevent injection attacks.",
               "preventive"),
        ]),
        _r("Repudiation", "R", [
            _t("threat-ds-r-001", "Audit Trail Gaps",
               "Changes to critical data records are not captured in an audit log.",
               "medium"),
            _t("threat-ds-r-002", "Unauthorized Backup Access",
               "Attacker accesses or modifies database backups without detection.",
               "high"),
        ], [
            _m("mit-ds-r-001", "Database Activity Monitoring",
               "Enable query-level audit logging (e.g., RDS Enhanced Monitoring, Aurora Audit Log).",
               "detective"),
            _m("mit-ds-r-002", "Backup Encryption and Access Control",
               "Encrypt backups and restrict access via IAM policies with MFA delete on S3.",
               "preventive"),
        ]),
        _r("InformationDisclosure", "I", [
            _t("threat-ds-i-001", "Data Exfiltration",
               "Attacker extracts sensitive data from the store via unauthorized read access or side-channel.",
               "critical"),
            _t("threat-ds-i-002", "Excessive Data in Responses",
               "Queries return more columns/records than needed, increasing exposure surface.",
               "medium"),
        ], [
            _m("mit-ds-i-001", "Column-Level Encryption and Data Masking",
               "Mask or encrypt sensitive columns (PII, PAN, credentials) at the database level.",
               "preventive"),
            _m("mit-ds-i-002", "Network Isolation (VPC / Private Subnet)",
               "Place data stores in private subnets with no public internet access.",
               "preventive"),
        ]),
        _r("DenialOfService", "D", [
            _t("threat-ds-d-001", "Connection Pool Exhaustion",
               "Attacker opens a large number of connections, preventing legitimate clients from connecting.",
               "high"),
            _t("threat-ds-d-002", "Storage Quota Abuse",
               "Attacker writes large volumes of data to fill up storage quota, causing service disruption.",
               "medium"),
        ], [
            _m("mit-ds-d-001", "Connection Limits and Pooling",
               "Configure maximum connection limits and use connection pooling (e.g., RDS Proxy).",
               "preventive"),
            _m("mit-ds-d-002", "Storage Quotas and Alerts",
               "Set storage quotas and CloudWatch alarms to detect abnormal growth patterns.",
               "detective"),
        ]),
    ],
    total_threats=8,
)

# ---------------------------------------------------------------------------
# Fixture: data_flow
# Categorias aplicáveis: T, I, D
# ---------------------------------------------------------------------------

FIXTURE_DATA_FLOW = KGQueryResult(
    element_type="data_flow",
    cloud_service=None,
    query_source="taxonomy",
    stride_results=[
        _r("Tampering", "T", [
            _t("threat-df-t-001", "Man-in-the-Middle Attack",
               "Attacker intercepts and modifies data while it flows between two endpoints.",
               "critical"),
            _t("threat-df-t-002", "Message Replay Attack",
               "Attacker captures and replays valid messages to trigger unintended operations.",
               "high"),
        ], [
            _m("mit-df-t-001", "TLS with Certificate Pinning",
               "Enforce TLS 1.2+ and optionally pin certificates for sensitive service-to-service flows.",
               "preventive"),
            _m("mit-df-t-002", "Message Signing and Nonce",
               "Sign messages with HMAC or asymmetric keys and include a nonce or timestamp to prevent replay.",
               "preventive"),
        ]),
        _r("InformationDisclosure", "I", [
            _t("threat-df-i-001", "Eavesdropping",
               "Attacker passively observes unencrypted data flows to capture sensitive information.",
               "high"),
            _t("threat-df-i-002", "Header and Metadata Leakage",
               "HTTP headers, query parameters or URL paths expose sensitive tokens or internal details.",
               "medium"),
        ], [
            _m("mit-df-i-001", "End-to-End Encryption",
               "Encrypt data flows end-to-end; do not terminate TLS at a proxy without re-encryption.",
               "preventive"),
            _m("mit-df-i-002", "Sensitive Data in Headers Policy",
               "Avoid placing secrets in URLs or query strings; use Authorization headers with short-lived tokens.",
               "preventive"),
        ]),
        _r("DenialOfService", "D", [
            _t("threat-df-d-001", "Traffic Flooding",
               "Attacker generates massive traffic to saturate network links or endpoints.",
               "high"),
            _t("threat-df-d-002", "Slow Connection Attack",
               "Attacker opens many connections and sends data very slowly, tying up server threads.",
               "medium"),
        ], [
            _m("mit-df-d-001", "DDoS Protection (AWS Shield / WAF)",
               "Enable AWS Shield Standard/Advanced and WAF rate-based rules to absorb flooding attacks.",
               "preventive"),
            _m("mit-df-d-002", "Connection Timeout Policies",
               "Configure aggressive connection timeouts and keepalive settings to drop slow connections.",
               "preventive"),
        ]),
    ],
    total_threats=6,
)

# ---------------------------------------------------------------------------
# Fixture: external_entity
# Categorias aplicáveis: S, R
# ---------------------------------------------------------------------------

FIXTURE_EXTERNAL_ENTITY = KGQueryResult(
    element_type="external_entity",
    cloud_service=None,
    query_source="taxonomy",
    stride_results=[
        _r("Spoofing", "S", [
            _t("threat-ee-s-001", "External Entity Impersonation",
               "Attacker impersonates a legitimate external user, partner or third-party system.",
               "high"),
            _t("threat-ee-s-002", "Phishing / Social Engineering",
               "Attacker tricks external users into revealing credentials or performing malicious actions.",
               "high"),
        ], [
            _m("mit-ee-s-001", "Strong Authentication for External Parties",
               "Enforce MFA and certificate-based authentication for all external integrations.",
               "preventive"),
            _m("mit-ee-s-002", "Security Awareness Training",
               "Train users to recognize phishing attempts; implement email filtering and DMARC/DKIM.",
               "preventive"),
        ]),
        _r("Repudiation", "R", [
            _t("threat-ee-r-001", "Transaction Repudiation",
               "External party denies having initiated a transaction, with no proof of interaction.",
               "medium"),
            _t("threat-ee-r-002", "Audit Log Inaccessibility",
               "Interaction logs from external entities are incomplete or inaccessible during disputes.",
               "medium"),
        ], [
            _m("mit-ee-r-001", "Non-Repudiation via Digital Signatures",
               "Require external parties to sign API requests; retain signed payloads as legal evidence.",
               "preventive"),
            _m("mit-ee-r-002", "Centralized Audit Logging",
               "Capture all external interactions in an immutable centralized log (CloudTrail, API Gateway logs).",
               "detective"),
        ]),
    ],
    total_threats=4,
)

# ---------------------------------------------------------------------------
# Lookup conveniente por element_type
# ---------------------------------------------------------------------------

FIXTURES_BY_ELEMENT_TYPE: dict[str, KGQueryResult] = {
    "process":         FIXTURE_PROCESS,
    "data_store":      FIXTURE_DATA_STORE,
    "data_flow":       FIXTURE_DATA_FLOW,
    "external_entity": FIXTURE_EXTERNAL_ENTITY,
}


def get_fixture_for(element_type: str) -> KGQueryResult:
    """
    Retorna o fixture de KGQueryResult para o element_type indicado.
    Usado por Dev 3 para mockar get_stride_threats() durante a Semana 1.

    Raises:
        KeyError: Se element_type não for um dos 4 tipos válidos.
    """
    if element_type not in FIXTURES_BY_ELEMENT_TYPE:
        raise KeyError(
            f"No fixture for element_type='{element_type}'. "
            f"Valid values: {list(FIXTURES_BY_ELEMENT_TYPE.keys())}"
        )
    return FIXTURES_BY_ELEMENT_TYPE[element_type]
