# Desenvolvimento local

## Subir tudo via Docker

```bash
cp .env.example .env
# preencher ANTHROPIC_API_KEY / OPENAI_API_KEY / NEO4J_PASSWORD no .env
docker compose up --build
```

- API: http://localhost:8000/api/v1/health
- Streamlit: http://localhost:8501
- Neo4j Browser: http://localhost:7474

## Subir apenas o Neo4j (fluxo Dev 2 / Dev 3)

```bash
docker compose up neo4j
```

Depois, rodar o seed da taxonomia STRIDE:

```bash
docker compose exec api python -m knowledge.taxonomy_seed
```

## Rodar a API fora do Docker

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

## Rodar os testes

```bash
pytest                     # testes unitários (rápidos, sem Neo4j)
pytest -m integration      # testes que dependem de Neo4j real (Docker precisa estar de pé)
```

## Variáveis de ambiente

Ver `.env.example` — todas documentadas ali. Nenhuma credencial deve ser commitada; `.env` está no `.gitignore`.

## Portas

Configuráveis via `.env` (`API_PORT`, `STREAMLIT_PORT`, `NEO4J_BROWSER_PORT`, `NEO4J_BOLT_PORT`) caso haja conflito no ambiente de avaliação.
