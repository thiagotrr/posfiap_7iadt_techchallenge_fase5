"""
knowledge/graph_schema.py

Constantes de labels de nós, tipos de relacionamento e mapeamento de serviços
de nuvem para o Knowledge Graph Neo4j do STRIDE Analyzer.

Os valores de CLOUD_SERVICES são os nomes canônicos usados como CloudService.name
no KG e devem coincidir exatamente com os valores do campo `cloud_service` do
schema Pydantic de Dev 1 (ArchitectureDiagram.Component.cloud_service).

Aliases completos importados de cloud_services.py na raiz do projeto.
"""

from cloud_services import cloud_service_aliases

# ---------------------------------------------------------------------------
# Labels de nós Neo4j
# ---------------------------------------------------------------------------

NODE_ELEMENT_TYPE = "ElementType"
NODE_STRIDE_CATEGORY = "STRIDECategory"
NODE_THREAT = "Threat"
NODE_MITIGATION = "Mitigation"
NODE_CLOUD_SERVICE = "CloudService"
NODE_SOURCE = "Source"

# ---------------------------------------------------------------------------
# Tipos de relacionamento Neo4j
# ---------------------------------------------------------------------------

REL_SUSCETIVEL_A = "SUSCETIVEL_A"          # (:ElementType)-[:SUSCETIVEL_A {severity}]->(:STRIDECategory)
REL_INCLUI_AMEACA = "INCLUI_AMEACA"        # (:STRIDECategory)-[:INCLUI_AMEACA]->(:Threat)
REL_MITIGADA_POR = "MITIGADA_POR"          # (:Threat)-[:MITIGADA_POR]->(:Mitigation)
REL_INSTANCIA_DE = "INSTANCIA_DE"          # (:CloudService)-[:INSTANCIA_DE]->(:ElementType)
REL_REFERENCIADA_EM = "REFERENCIADA_EM"    # (:Mitigation)-[:REFERENCIADA_EM]->(:Source)

# Relacionamentos usados pelo pipeline de ingestão (Épicos 2–3)
REL_COVERS_SERVICE = "COVERS_SERVICE"      # (:Source)-[:COVERS_SERVICE]->(:CloudService)
REL_COVERS_CATEGORY = "COVERS_CATEGORY"   # (:Source)-[:COVERS_CATEGORY]->(:STRIDECategory)
REL_HAS_SPECIFIC_THREAT = "HAS_SPECIFIC_THREAT"
REL_HAS_SPECIFIC_MITIGATION = "HAS_SPECIFIC_MITIGATION"

# Aliases legados do contrato inicial; mantidos para imports existentes.
REL_POSSUI_AMEACA_ESPECIFICA = REL_HAS_SPECIFIC_THREAT
REL_POSSUI_MITIGACAO_ESPECIFICA = REL_HAS_SPECIFIC_MITIGATION

# ---------------------------------------------------------------------------
# Valores canônicos de ElementType
# Os mesmos literals do campo element_type no schema Pydantic do Dev 1.
# ---------------------------------------------------------------------------

ELEMENT_TYPE_PROCESS = "process"
ELEMENT_TYPE_DATA_STORE = "data_store"
ELEMENT_TYPE_DATA_FLOW = "data_flow"
ELEMENT_TYPE_EXTERNAL_ENTITY = "external_entity"

ELEMENT_TYPES: list[str] = [
    ELEMENT_TYPE_PROCESS,
    ELEMENT_TYPE_DATA_STORE,
    ELEMENT_TYPE_DATA_FLOW,
    ELEMENT_TYPE_EXTERNAL_ENTITY,
]

# ---------------------------------------------------------------------------
# Valores canônicos de STRIDECategory
# ---------------------------------------------------------------------------

STRIDE_LETTERS: list[str] = ["S", "T", "R", "I", "D", "E"]

STRIDE_CATEGORY_NAMES: dict[str, str] = {
    "S": "Spoofing",
    "T": "Tampering",
    "R": "Repudiation",
    "I": "InformationDisclosure",
    "D": "DenialOfService",
    "E": "ElevationOfPrivilege",
}

# ---------------------------------------------------------------------------
# Matriz STRIDE por ElementType (método Microsoft)
# Fonte: https://learn.microsoft.com/en-us/azure/security/develop/threat-modeling-tool-threats
#
# ElementType    | S | T | R | I | D | E
# ---------------|---|---|---|---|---|---
# process        | ✓ | ✓ | ✓ | ✓ | ✓| ✓
# data_store     |   | ✓ | ✓ | ✓ | ✓|
# data_flow      |   | ✓ |   | ✓ | ✓ |
# external_entity| ✓ |   | ✓ |   |   |
# ---------------------------------------------------------------------------

STRIDE_MATRIX: dict[str, list[str]] = {
    ELEMENT_TYPE_PROCESS:         ["S", "T", "R", "I", "D", "E"],
    ELEMENT_TYPE_DATA_STORE:      ["T", "R", "I", "D"],
    ELEMENT_TYPE_DATA_FLOW:       ["T", "I", "D"],
    ELEMENT_TYPE_EXTERNAL_ENTITY: ["S", "R"],
}

# ---------------------------------------------------------------------------
# CLOUD_SERVICES
#
# Mapeamento de aliases/variantes → nome canônico usado como CloudService.name
# no KG. Os valores devem coincidir EXATAMENTE com o campo `cloud_service` que
# o LLM de extração (Dev 1) produz. Nomes sourced de cloud_services.py.
# ---------------------------------------------------------------------------

CLOUD_SERVICES: dict[str, str] = cloud_service_aliases

# Conjunto de nomes canônicos únicos presentes no KG (usado para validação)
CANONICAL_CLOUD_SERVICE_NAMES: set[str] = set(CLOUD_SERVICES.values())

# Lista ordenada dos serviços presentes no diagrama de referência da arquitetura
# (json-referência_arquitetura.json) usados no seed da taxonomia.
REFERENCE_ARCHITECTURE_SERVICES: list[dict] = [
    {"name": "Route 53",              "provider": "aws", "element_type": ELEMENT_TYPE_PROCESS,         "category": "networking"},
    {"name": "Elastic Load Balancing","provider": "aws", "element_type": ELEMENT_TYPE_PROCESS,         "category": "networking"},
    {"name": "EC2",                   "provider": "aws", "element_type": ELEMENT_TYPE_PROCESS,         "category": "compute"},
    {"name": "ElastiCache",           "provider": "aws", "element_type": ELEMENT_TYPE_DATA_STORE,      "category": "database"},
    {"name": "RDS",                   "provider": "aws", "element_type": ELEMENT_TYPE_DATA_STORE,      "category": "database"},
    {"name": "S3",                    "provider": "aws", "element_type": ELEMENT_TYPE_DATA_STORE,      "category": "storage"},
    {"name": "CloudFront",            "provider": "aws", "element_type": ELEMENT_TYPE_PROCESS,         "category": "networking"},
    {"name": "CloudWatch",            "provider": "aws", "element_type": ELEMENT_TYPE_PROCESS,         "category": "monitoring"},
    {"name": "SNS",                   "provider": "aws", "element_type": ELEMENT_TYPE_PROCESS,         "category": "integration"},
    {"name": "DynamoDB",              "provider": "aws", "element_type": ELEMENT_TYPE_DATA_STORE,      "category": "database"},
    {"name": "SES",                   "provider": "aws", "element_type": ELEMENT_TYPE_PROCESS,         "category": "integration"},
]
