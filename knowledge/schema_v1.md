# Knowledge Graph STRIDE — Schema v1

## Visão Geral

O Knowledge Graph é a base de conhecimento determinística do STRIDE Analyzer.
Armazena a taxonomia canônica Microsoft (ElementType → STRIDECategory → Threat → Mitigation)
e os serviços de nuvem do diagrama de referência como nós `CloudService`.

---

## Labels de Nós

| Label | Campos | Valores / Tipo |
|---|---|---|
| `ElementType` | `id`, `name`, `description` | `process`, `data_store`, `data_flow`, `external_entity` |
| `STRIDECategory` | `id`, `letter`, `name`, `description` | S/T/R/I/D/E |
| `Threat` | `id`, `name`, `description`, `severity` | severity: critical/high/medium/low |
| `Mitigation` | `id`, `name`, `description`, `control_type` | control_type: preventive/detective/corrective |
| `CloudService` | `id`, `name`, `provider`, `element_type`, `category` | provider: aws/azure/gcp/generic |
| `Source` | `id`, `url`, `title`, `crawled_at`, `stride_tags` | crawled_at: ISO-8601 |

---

## Tipos de Relacionamento

| Relacionamento | De → Para | Propriedades |
|---|---|---|
| `SUSCETIVEL_A` | `ElementType` → `STRIDECategory` | `severity: str` |
| `INCLUI_AMEACA` | `STRIDECategory` → `Threat` | — |
| `MITIGADA_POR` | `Threat` → `Mitigation` | — |
| `INSTANCIA_DE` | `CloudService` → `ElementType` | — |
| `POSSUI_AMEACA_ESPECIFICA` | `CloudService` → `Threat` | — |
| `POSSUI_MITIGACAO_ESPECIFICA` | `CloudService` → `Mitigation` | — |
| `REFERENCIADA_EM` | `Mitigation` → `Source` | — |
| `COVERS_SERVICE` | `Source` → `CloudService` | — |
| `COVERS_CATEGORY` | `Source` → `STRIDECategory` | — |

---

## Matriz STRIDE por ElementType (Método Microsoft)

| ElementType | S | T | R | I | D | E |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| `process` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `data_store` | | ✓ | ✓ | ✓ | ✓ | |
| `data_flow` | | ✓ | | ✓ | ✓ | |
| `external_entity` | ✓ | | ✓ | | | |

---

## Queries Cypher Canônicas

### Query 1 — Categorias STRIDE aplicáveis a um ElementType

```cypher
MATCH (et:ElementType {id: $element_type})
      -[:SUSCETIVEL_A]->(sc:STRIDECategory)
RETURN sc.letter, sc.name, sc.description
ORDER BY sc.letter
```

**Uso esperado (Dev 3):** nó de retrieval usa `element_type` do componente atual
para descobrir quais categorias STRIDE são aplicáveis.

---

### Query 2 — Ameaças e mitigações por ElementType (taxonomia completa)

```cypher
MATCH (et:ElementType {id: $element_type})
      -[:SUSCETIVEL_A]->(sc:STRIDECategory)
      -[:INCLUI_AMEACA]->(t:Threat)
      -[:MITIGADA_POR]->(m:Mitigation)
RETURN sc.letter       AS category_letter,
       sc.name          AS category_name,
       t.id             AS threat_id,
       t.name           AS threat_name,
       t.description    AS threat_description,
       t.severity       AS severity,
       m.id             AS mitigation_id,
       m.name           AS mitigation_name,
       m.description    AS mitigation_description,
       m.control_type   AS control_type
ORDER BY sc.letter, t.severity DESC
```

**Uso esperado (Dev 3):** resultado base para o contexto do LLM de geração
de ameaças (campo `kg_context` no prompt).

---

### Query 3 — Enriquecimento por serviço de nuvem

```cypher
MATCH (cs:CloudService {name: $cloud_service})
      -[:INSTANCIA_DE]->(et:ElementType {id: $element_type})
      -[:SUSCETIVEL_A]->(sc:STRIDECategory)
      -[:INCLUI_AMEACA]->(t:Threat)
      -[:MITIGADA_POR]->(m:Mitigation)
OPTIONAL MATCH (cs)-[:POSSUI_AMEACA_ESPECIFICA]->(specific_t:Threat)
OPTIONAL MATCH (specific_t)-[:MITIGADA_POR]->(specific_m:Mitigation)
RETURN sc.letter, sc.name,
       collect(DISTINCT t)          AS taxonomy_threats,
       collect(DISTINCT m)          AS taxonomy_mitigations,
       collect(DISTINCT specific_t) AS specific_threats,
       collect(DISTINCT specific_m) AS specific_mitigations
ORDER BY sc.letter
```

**Uso esperado (Dev 3):** quando `cloud_service` é fornecido, combina
taxonomia base com ameaças específicas do serviço.

---

### Query 4 — Health-check (contagem de nós)

```cypher
MATCH (et:ElementType) WITH count(et) AS element_types
MATCH (sc:STRIDECategory) WITH element_types, count(sc) AS stride_categories
MATCH (t:Threat) WITH element_types, stride_categories, count(t) AS threats
MATCH (m:Mitigation) WITH element_types, stride_categories, threats, count(m) AS mitigations
RETURN element_types, stride_categories, threats, mitigations
```

**Uso esperado (Dev 4):** endpoint `GET /api/v1/knowledge/health`.

---

## CloudServices no Seed (Diagrama de Referência)

| name | provider | element_type | category |
|---|---|---|---|
| Route 53 | aws | process | networking |
| Elastic Load Balancing | aws | process | networking |
| EC2 | aws | process | compute |
| ElastiCache | aws | data_store | database |
| RDS | aws | data_store | database |
| S3 | aws | data_store | storage |
| CloudFront | aws | process | networking |
| CloudWatch | aws | process | monitoring |
| SNS | aws | process | integration |
| DynamoDB | aws | data_store | database |
| SES | aws | process | integration |
| External Entity | generic | external_entity | external |

---

## Como Popular o Neo4j (Seed)

```bash
# 1. Defina as variáveis de ambiente
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=sua_senha

# 2. Execute o seed
python scripts/seed_kg.py

# OU via módulo
python -m knowledge.taxonomy_seed
```

Execução esperada:
```
2024-01-01 00:00:00 [INFO] knowledge.taxonomy_seed — KG seed started — uri=bolt://localhost:7687
2024-01-01 00:00:01 [INFO] knowledge.taxonomy_seed — KG seed completed — nodes_created=30 relationships_created=48
```

O seed é **idempotente** — executar novamente não duplica nós (usa `MERGE`).

---

## Verificação pós-seed (Neo4j Browser)

Acesse `http://localhost:7474` com `neo4j / sua_senha` e execute:

```cypher
// Contagem de nós
MATCH (n) RETURN labels(n)[0] AS label, count(n) AS total ORDER BY label

// Visualizar grafo completo da taxonomia
MATCH (et:ElementType)-[:SUSCETIVEL_A]->(sc:STRIDECategory)
      -[:INCLUI_AMEACA]->(t:Threat)-[:MITIGADA_POR]->(m:Mitigation)
RETURN et, sc, t, m LIMIT 50
```
