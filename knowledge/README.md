# knowledge/ — Módulo de Base de Conhecimento STRIDE

## Visão Geral

Módulo Dev 2. Gerencia o Knowledge Graph Neo4j com:
- Taxonomia STRIDE determinística (4 `ElementType`, 6 `STRIDECategory`, 12 `Threat`, 12 `Mitigation`)
- Serviços de nuvem do diagrama de referência (11 nós `CloudService` AWS + 1 External Entity genérico)
- Crawler e pipeline condicional de classificação/enriquecimento
- Interface de query `get_stride_threats()` consumida pelo LangGraph (Dev 3)

---

## Início Rápido

### 1. Neo4j local (sem Docker do Dev 4)

```bash
# Opção A — Neo4j instalado localmente
# Inicie o serviço e defina as variáveis:
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=sua_senha

# Opção B — Docker rápido (sem persistência)
docker run --name neo4j-dev -d \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:5-community
export NEO4J_PASSWORD=password
```

### 2. Popular o KG (seed)

```bash
python scripts/seed_kg.py
```

### 3. Usar os fixtures (sem Neo4j)

```python
from knowledge.fixtures import get_fixture_for

result = get_fixture_for("process")
print(result.total_threats)          # 12
print(result.stride_results[0].letter)  # "S"
```

### 4. Executar a ingestão

O classificador usa LangChain e aceita OpenAI ou Gemini. Configure apenas um
provedor e sua chave no ambiente:

```bash
# OpenAI
export KG_CLASSIFIER_LLM_PROVIDER=openai
export OPENAI_API_KEY=...

# ou Gemini
export KG_CLASSIFIER_LLM_PROVIDER=gemini
export GOOGLE_API_KEY=...

python scripts/run_ingestion.py
python scripts/run_ingestion.py --force
```

`KG_CLASSIFIER_LLM_PROVIDER` tem precedência sobre
`EXTRACTION_LLM_PROVIDER`. Se a chamada ao LLM falhar, o pipeline usa
heurísticas locais e, por fim, os `stride_hint` do crawler.

---

## API Pública

### `get_stride_threats()`

```python
from knowledge import get_stride_threats

# Apenas taxonomia base
result = get_stride_threats("data_store")

# Com enriquecimento por serviço
result = get_stride_threats("data_store", cloud_service="RDS")

# result: KGQueryResult
result.element_type      # "data_store"
result.total_threats     # n
result.query_source      # "taxonomy" | "enriched" | "both"
result.stride_results    # list[STRIDEResult]
```

A função valida o `element_type`, normaliza aliases de serviços (por exemplo,
`Amazon S3` → `S3`) e combina a taxonomia com os relacionamentos de
enriquecimento criados pelo pipeline. Um resultado só é marcado como
enriquecido quando os vínculos de `Source` para o serviço e a categoria também
existem; o contrato Pydantic publicado no Épico 1 permanece inalterado.

### Modelos Pydantic (`knowledge/models.py`)

| Modelo | Descrição |
|---|---|
| `ThreatResult` | Ameaça: id, name, description, severity |
| `MitigationResult` | Mitigação: id, name, description, control_type |
| `STRIDEResult` | Categoria STRIDE com listas de threats e mitigations |
| `KGQueryResult` | Resultado completo: element_type, stride_results, total_threats, query_source |

---

## Como Mockar no Dev 3 / Dev 4

```python
from unittest.mock import patch
import knowledge
from knowledge.fixtures import get_fixture_for

with patch.object(knowledge, "get_stride_threats", side_effect=get_fixture_for):
    result = knowledge.get_stride_threats("process")
```

---

## Estrutura de Arquivos

```
knowledge/
├── __init__.py          # Exporta: get_stride_threats, run_ingestion, KGQueryResult
├── graph_schema.py      # Constantes de labels, relationships, CLOUD_SERVICES
├── graph_client.py      # Singleton Neo4j driver
├── models.py            # ThreatResult, MitigationResult, STRIDEResult, KGQueryResult
├── query.py             # get_stride_threats() — taxonomia + enriquecimento
├── taxonomy_seed.py     # run_seed() — popula taxonomia STRIDE
├── exceptions.py        # ElementTypeNotFoundError, IngestionError, CrawlerError
├── fixtures.py          # Fixtures para mock (Dev 3 / Dev 4)
├── router.py            # APIRouter FastAPI GET /knowledge/health
├── schema_v1.md         # Schema documentado + Cypher queries
├── graph_schema_v1.json # Snapshot do schema (contrato JSON para outros devs)
├── ingestion/           # Classificador, loader e pipeline condicional
└── crawler/             # Web crawler e persistência do corpus
```

---

## Limitações Conhecidas (MVP)

- `MemorySaver` do driver Neo4j é per-processo — múltiplos workers FastAPI criam drivers separados.
- Taxonomia STRIDE é baseada no método Microsoft; ameaças por serviço específico dependem do crawler (Épico 2+3).
- Sem `crawl_manifest.json`, a ingestão executa somente o seed e termina com sucesso.

---

## Variáveis de Ambiente

| Variável | Default | Descrição |
|---|---|---|
| `NEO4J_URI` | `bolt://localhost:7687` | URI do Neo4j |
| `NEO4J_USER` | `neo4j` | Usuário Neo4j |
| `NEO4J_PASSWORD` | — | **Obrigatória** |
| `NEO4J_DATABASE` | `neo4j` | Database usada pelo Singleton |
| `KG_CLASSIFIER_LLM_PROVIDER` | `openai` | `openai` ou `gemini` |
| `OPENAI_API_KEY` | — | Chave usada pelo provider OpenAI |
| `GOOGLE_API_KEY` / `GEMINI_API_KEY` | — | Chave usada pelo provider Gemini |
| `KG_CLASSIFIER_OPENAI_MODEL` | `gpt-4o-mini` | Modelo OpenAI |
| `KG_CLASSIFIER_GEMINI_MODEL` | `gemini-2.5-flash` | Modelo Gemini |

---

## Testes

```bash
# Testes unitários, sem infraestrutura externa
pytest -m "not integration"

# Testes de integração (execute a partir do host)
docker compose up -d neo4j
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=password
pytest -m integration
```

O router é testado em uma aplicação FastAPI isolada e permanece sem registro
no app principal; sua montagem em `/api/v1` é responsabilidade do Dev 4.
