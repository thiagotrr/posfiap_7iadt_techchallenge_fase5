# Dev 2 — Testes Manuais e Pipeline Fim-a-Fim

Guia passo a passo para executar o fluxo completo do **Dev 2** (Knowledge Graph STRIDE):
crawler, ingestão Neo4j, validação Cypher e visualização de grafos.

> **Data da execução de referência:** 2026-07-21  
> **Ambiente:** Windows 11, Python 3.13, Docker Desktop, Neo4j 5 Community

---

## Pré-requisitos

| Item | Versão / Detalhe |
|------|------------------|
| Python | 3.11+ (venv recomendado) |
| Docker Desktop | Para Neo4j 5 Community |
| Git | Repositório clonado |
| Internet | Necessária para crawler completo (~6 min) |
| LLM API key | Opcional — classificador usa fallback heurístico sem chave |

---

## 1. Atualizar o repositório

```powershell
cd D:\Repos\FiapIADevs\techchallenge_fase5\posfiap_7iadt_techchallenge_fase5
git pull origin main
```

---

## 2. Configurar ambiente

```powershell
# Criar e ativar venv (se ainda não existir)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Instalar dependências
pip install -r requirements.txt

# Copiar variáveis de ambiente
Copy-Item .env.example .env
# Editar .env: NEO4J_PASSWORD=password (mínimo)
# Opcional: OPENAI_API_KEY=sk-... para classificação LLM
```

**Importante (Windows):** ao rodar scripts do **host**, use `NEO4J_URI=bolt://localhost:7687`  
(no `.env.example` o default `bolt://neo4j:7687` é para containers Docker).

---

## 3. Subir o Neo4j

```powershell
docker compose up -d neo4j
```

Aguarde o healthcheck (≈30 s). Verifique:

```powershell
docker compose ps neo4j
# STATUS deve mostrar "healthy"
```

Acesse o **Neo4j Browser:** http://localhost:7474  
Credenciais: `neo4j` / `password` (ou valor de `NEO4J_PASSWORD` no `.env`)

---

## 4. Executar o Crawler completo (Épico 2)

> Atenção para a opção em "Alternativa rápida"

O crawler coleta documentação pública de 4 fontes de segurança:

| Fonte | Provider | Documentos (exec. 2026-07-21) |
|-------|----------|--------------------------------|
| AWS Well-Architected Security Pillar | `aws` | 9 |
| Azure Security Fundamentals | `azure` | 60 |
| Microsoft STRIDE Threat Categories | `microsoft` | 3 |
| OWASP Threat Modeling Cheat Sheet | `owasp` | 120 |
| **Total** | | **195** |

```powershell
# Workaround SSL no Windows dev (se necessário)
$env:KG_CRAWL_SSL_VERIFY = "false"

# Executar crawler (~6 minutos)
python scripts/run_crawler.py
```

**Saída esperada:**

```
=== Crawl Summary ===
Targets processed : 4
Documents saved   : 192 (new this run)
Total in storage  : 195
By provider       : {'aws': 10, 'azure': 60, 'microsoft': 4, 'owasp': 121}
Corpus size       : ~2,598,780 characters
```

Artefatos gerados:

- `data/crawled/{provider}/{content_hash}.json` — documentos individuais
- `data/crawled/crawl_manifest.json` — manifesto para a ingestão

### Alternativa rápida (sem internet)

```powershell
python scripts/bootstrap_sample_corpus.py
# Copia 3 documentos de tests/fixtures/sample_corpus/
```

---

## 5. Ingestão no Neo4j (Épico 3)

O pipeline de ingestão:

1. Verifica se a taxonomia STRIDE está seedada (4 ElementTypes, 6 STRIDECategories)
2. Executa seed se necessário (`knowledge/taxonomy_seed.py`)
3. Classifica cada documento (LLM → heurística → `stride_hint` do crawler)
4. Cria nós `Source` e relacionamentos `COBRE_SERVICO`, `COBRE_CATEGORIA`

```powershell
$env:NEO4J_URI = "bolt://localhost:7687"
$env:NEO4J_PASSWORD = "password"

# Primeira execução (seed + ingestão automática)
python scripts/run_ingestion.py

# Re-ingestão forçada (KG já populado)
python scripts/run_ingestion.py --force
```

**Resultado da execução de referência (2026-07-21):**

```
status=completed processed=195 failed=0 elapsed=26.32s
```

> **Nota:** sem `OPENAI_API_KEY`, o classificador LLM falha com `ModuleNotFoundError`
> (LangChain OpenAI não instalado) e usa fallback heurístico + `stride_hint`.
> A ingestão completa funciona normalmente.

---

## 6. Validação com queries Cypher

### 6.1 Via script automatizado

```powershell
python scripts/validate_kg.py
python scripts/validate_kg.py --graph-sample 30 --export data/kg_sample.json
```

### 6.2 Via Neo4j Browser (http://localhost:7474)

#### Query 4 — Health-check (taxonomia base)

Esperado pós-seed: `4, 6, 12, 12`

```cypher
MATCH (et:ElementType) WITH count(et) AS element_types
MATCH (sc:STRIDECategory) WITH element_types, count(sc) AS stride_categories
MATCH (t:Threat) WITH element_types, stride_categories, count(t) AS threats
MATCH (m:Mitigation) WITH element_types, stride_categories, threats, count(m) AS mitigations
RETURN element_types, stride_categories, threats, mitigations
```

#### Contagem de nós por label (pós-ingestão)

```cypher
MATCH (n) RETURN labels(n)[0] AS label, count(n) AS total ORDER BY label
```

**Resultado esperado (exec. 2026-07-21):**

| Label | Total |
|-------|-------|
| CloudService | 12 |
| ElementType | 4 |
| Mitigation | 12 |
| STRIDECategory | 6 |
| **Source** | **195** |
| Threat | 12 |

#### Query 1 — Categorias STRIDE para `data_store`

```cypher
MATCH (et:ElementType {id: 'data_store'})
      -[:SUSCETIVEL_A]->(sc:STRIDECategory)
RETURN sc.letter, sc.name, sc.description
ORDER BY sc.letter
```

Resultado: `[D] DenialOfService`, `[I] InformationDisclosure`, `[R] Repudiation`, `[T] Tampering`

#### Query 2 — Ameaças e mitigações (taxonomia completa)

```cypher
MATCH (et:ElementType {id: 'process'})
      -[:SUSCETIVEL_A]->(sc:STRIDECategory)
      -[:INCLUI_AMEACA]->(t:Threat)
      -[:MITIGADA_POR]->(m:Mitigation)
RETURN sc.letter AS category, t.name AS threat, t.severity AS severity,
       m.name AS mitigation
ORDER BY sc.letter, t.severity DESC
LIMIT 20
```

#### Enriquecimento pós-ingestão

```cypher
MATCH (source:Source)
RETURN count(source) AS total_sources

MATCH (source:Source)-[:COBRE_CATEGORIA]->(sc:STRIDECategory)
RETURN sc.letter, count(source) AS docs
ORDER BY docs DESC
```

---

## 7. Visualização de grafos

### Grafo 1 — Taxonomia STRIDE completa

No Neo4j Browser, execute:

```cypher
MATCH (et:ElementType)-[:SUSCETIVEL_A]->(sc:STRIDECategory)
      -[:INCLUI_AMEACA]->(t:Threat)-[:MITIGADA_POR]->(m:Mitigation)
RETURN et, sc, t, m LIMIT 50
```

Clique em **Graph** para visualizar a árvore ElementType → STRIDE → Threat → Mitigation.

### Grafo 2 — CloudServices e taxonomia

```cypher
MATCH (cs:CloudService)-[:INSTANCIA_DE]->(et:ElementType)
      -[:SUSCETIVEL_A]->(sc:STRIDECategory)
RETURN cs, et, sc LIMIT 30
```

### Grafo 3 — Enriquecimento (Sources + categorias)

```cypher
MATCH (source:Source)-[:COBRE_CATEGORIA]->(sc:STRIDECategory)
RETURN source, sc LIMIT 25
```

### Grafo 4 — Subgrafo de um serviço específico

```cypher
MATCH (cs:CloudService {name: 'S3'})-[:INSTANCIA_DE]->(et:ElementType)
      -[:SUSCETIVEL_A]->(sc:STRIDECategory)
      -[:INCLUI_AMEACA]->(t:Threat)
OPTIONAL MATCH (source:Source)-[:COBRE_SERVICO]->(cs)
RETURN cs, et, sc, t, source
```

---

## 8. Script consolidado fim-a-fim

Um único comando executa todo o pipeline Dev 2:

```powershell
# Pipeline completo (Neo4j + crawl + ingestão + validação)
python scripts/run_dev2_pipeline.py

# Opções úteis
python scripts/run_dev2_pipeline.py --sample-corpus   # sem internet
python scripts/run_dev2_pipeline.py --skip-crawl        # usa corpus existente
python scripts/run_dev2_pipeline.py --force             # re-ingestão
python scripts/run_dev2_pipeline.py --validate-only     # só validação
```

Ver docstring completa: `scripts/run_dev2_pipeline.py`

---

## 9. Testes automatizados

```powershell
# Unitários (sem Neo4j)
pytest -m "not integration"

# Integração (Neo4j deve estar rodando)
$env:NEO4J_URI = "bolt://localhost:7687"
pytest -m integration

# Crawler e storage
pytest tests/test_crawler.py tests/test_storage.py -v
```

---

## 10. Troubleshooting

| Problema | Solução |
|----------|---------|
| `CERTIFICATE_VERIFY_FAILED` no crawl | `$env:KG_CRAWL_SSL_VERIFY="false"` |
| `NEO4J_PASSWORD not set` | Configure no `.env` |
| `Unable to connect to bolt://neo4j:7687` | Use `bolt://localhost:7687` do host |
| Ingestão `status=skipped` | Use `--force` ou limpe o grafo |
| LLM `ModuleNotFoundError` | Instale `langchain-openai` ou ignore (fallback funciona) |
| Neo4j não healthy | `docker compose logs neo4j` e aguarde ~30 s |

---

## Referências

- `knowledge/README.md` — módulo Dev 2
- `knowledge/schema_v1.md` — schema + queries Cypher canônicas
- `knowledge/crawler/README.md` — detalhes do crawler
- `.env.example` — variáveis de ambiente
- `scripts/run_dev2_pipeline.py` — script consolidado
- `scripts/validate_kg.py` — validação automatizada
