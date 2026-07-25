# Referência da API

Com a `api` no ar (`docker compose up` ou `uvicorn app.main:app --reload`), a
documentação interativa é gerada automaticamente pelo FastAPI a partir do
schema OpenAPI (`http://localhost:8000/openapi.json`):

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

Todas as rotas ficam sob o prefixo `/api/v1`.

## Health

| Rota | Descrição |
|---|---|
| `GET /api/v1/health` | Health-check global — `{"status", "version", "modules": {"extraction", "knowledge", "orchestration"}}` |

## Extração (Dev 1) — `/api/v1/extraction/`

| Rota | Descrição |
|---|---|
| `GET /health` | Status do serviço vision-detector (modo `http` ou `import`) |
| `POST /diagram` | Extrai `ArchitectureDiagram` de uma imagem (`multipart/form-data`, campo `image`) |
| `POST /diagram/patch` | Aplica um `DiagramPatch` (update/add/remove) a um diagrama já extraído |

Ver [`extraction/README.md`](../extraction/README.md) para o schema completo
de `ArchitectureDiagram` e `DiagramPatch`.

## Knowledge Graph (Dev 2) — `/api/v1/knowledge/`

Health-check e consulta de status do grafo Neo4j. Ver
[`knowledge/README.md`](../knowledge/README.md) para o schema da taxonomia
STRIDE e as consultas disponíveis.

## Orquestração STRIDE (Dev 3) — `/api/v1/orchestration/`

| Rota | Descrição |
|---|---|
| `GET /health` | Health-check |
| `POST /analyses` | Inicia uma análise (body: `ArchitectureDiagram`) — roda de forma síncrona até o checkpoint HITL, retorna `GraphStateResponse` |
| `GET /analyses/{thread_id}` | Estado atual da análise (polling, não avança o grafo) |
| `POST /analyses/{thread_id}/messages` | Decisão HITL — body `{"action": "approve"}` ou `{"action": "refine", "feedback": "..."}` |
| `GET /analyses/{thread_id}/report` | `STRIDEReport` final — `404` se ainda não disponível |

Ver [`orchestration/README.md`](../orchestration/README.md) para o ciclo de
vida completo do grafo LangGraph e as variáveis de configuração do LLM.
