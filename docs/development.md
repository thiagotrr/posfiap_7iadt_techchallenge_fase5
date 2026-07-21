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
- vision-detector (extração, uso interno da API): http://localhost:8001/health

## Extração de diagrama (vision-detector)

`POST /api/v1/extraction/diagram` recebe uma imagem de diagrama de arquitetura
e devolve o `ArchitectureDiagram` (JSON, contrato em `extraction/schemas.py`).
`POST /api/v1/extraction/diagram/patch` aplica correções HITL pontuais
(update/add/remove) num diagrama já extraído. Ver `extraction/README.md` para
o formato completo e `GET /api/v1/extraction/health` para checar o status.

Por padrão (`docker compose up`), a extração roda no serviço `vision-detector`
(container separado, mantém a imagem da `api` leve) e a `api` fala com ele via
HTTP usando a env `VISION_DETECTOR_URL` (já configurada no `docker-compose.yml`).

### Pesos do modelo: usar o pré-treinado ou treinar localmente

Duas opções, escolhidas automaticamente pelo que já existe em
`models/vision-detector/runs/detect/stride/weights/best.pt`:

1. **Usar o modelo pré-treinado (padrão, recomendado)** — não precisa do
   dataset. No primeiro `docker compose up`, o container `vision-detector`
   baixa os pesos automaticamente do Hugging Face Hub
   ([luisasousa/aws-architecture-vision-detector](https://huggingface.co/luisasousa/aws-architecture-vision-detector));
   se a rede falhar (ambiente offline), ele loga o comando de download manual
   em vez de derrubar o container. Para desligar até a *tentativa* de
   download (ex.: ambiente sempre offline), defina
   `VISION_DETECTOR_AUTO_DOWNLOAD_WEIGHTS=false` no `.env`.
2. **Treinar seu próprio modelo localmente** — precisa do dataset de treino
   (baixe do Roboflow ou do repo de dataset no Hugging Face
   [luisasousa/aws-architecture-diagrams](https://huggingface.co/datasets/luisasousa/aws-architecture-diagrams),
   ver [`models/vision-detector/README.md`](../models/vision-detector/README.md#modelo-e-dataset-no-hugging-face)).
   Depois: `docker compose run --rm vision-detector python train.py`. Pesos
   treinados localmente sempre têm prioridade — o download automático só
   roda quando `best.pt` está ausente, então treinar não é sobrescrito por
   ele.

`GET /api/v1/extraction/health` (ou `GET /health` direto no `vision-detector`,
porta `8001`) reporta se os pesos estão presentes.

### GPU (RTX 5070 / Blackwell)

Sem GPU, a inferência roda normalmente em CPU (~0,2s por imagem — só o
*treino* do modelo é impraticável sem GPU, não afeta quem só usa a API). Se
sua máquina tem uma RTX 5070 (ou outra GPU Blackwell), descomente o bloco
`deploy:` comentado no serviço `vision-detector` do `docker-compose.yml`
(é a mesma config usada no desenvolvimento deste modelo — requer o [NVIDIA
Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
no host). O `Dockerfile` do `vision-detector` já instala o build de torch com
CUDA 12.8 necessário para essa GPU. Detalhes em
[`models/vision-detector/README.md`](../models/vision-detector/README.md#gpu-nvidia-blackwell-ex-rtx-5070).

### Importar o modelo direto (sem Docker, sem HTTP)

Quem quiser chamar a extração direto no próprio processo Python — sem subir o
container `vision-detector` nem passar por HTTP —, não define
`VISION_DETECTOR_URL` no ambiente:

```bash
pip install -r extraction/requirements.txt
pip install -r models/vision-detector/requirements.txt  # torch/ultralytics/opencv/tesseract
```

```python
from extraction.service import extract_diagram

with open("meu_diagrama.png", "rb") as f:
    diagram = extract_diagram(f.read(), mime_type="image/png")
```

`extract_diagram` detecta a ausência da env e importa
`models/vision-detector/predict.py` direto no processo. Ver docstring de
`extraction/service.py` para os dois modos.

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
pytest                     # testes unitários (rápidos, sem Neo4j) -- tests/ e extraction/tests/
pytest -m integration      # testes que dependem de Neo4j real (Docker precisa estar de pé)

# models/vision-detector/tests/ fica de fora do `pytest` acima (precisa de
# torch/opencv, não são dependências do requirements.txt raiz) -- roda
# dentro do próprio container, que já tem essas dependências:
docker compose run --rm vision-detector pytest
```

## Variáveis de ambiente

Ver `.env.example` — todas documentadas ali. Nenhuma credencial deve ser commitada; `.env` está no `.gitignore`.

## Portas

Configuráveis via `.env` (`API_PORT`, `STREAMLIT_PORT`, `NEO4J_BROWSER_PORT`, `NEO4J_BOLT_PORT`, `VISION_DETECTOR_PORT`) caso haja conflito no ambiente de avaliação.
