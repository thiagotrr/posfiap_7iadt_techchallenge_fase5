# Detector de componentes de arquitetura (etapa de visão computacional)

Pipeline supervisionado que detecta componentes num diagrama de arquitetura AWS
e os classifica em **arquétipos**, que depois alimentam a modelagem STRIDE.

## Uso rápido: rodando o modelo já treinado (sem treinar do zero)

Se você só quer **usar** o modelo (gerar o `ArchitectureDiagram` de um
diagrama seu), não precisa baixar o dataset do Roboflow nem treinar nada —
basta os pesos já treinados. **Não precisa de GPU** para isso, só para
treinar (ver [Requisitos de hardware e tempo estimado](#requisitos-de-hardware-e-tempo-estimado)).

```bash
# 1. Baixe os pesos treinados do Hugging Face (ver link em
#    "Modelo e dataset no Hugging Face" abaixo) para
#    models/vision-detector/runs/detect/stride/weights/best.pt

# 2. Build da imagem Docker (uma vez só)
docker compose build vision-detector

# 3. Rode a inferência (a imagem de entrada deve estar em models/vision-detector/)
docker compose run --rm vision-detector python predict.py minha_arquitetura.png
```

Isso escreve `minha_arquitetura_architecture.json` (o `ArchitectureDiagram`
completo) e `deteccao_saida.jpg` (a imagem com as caixas desenhadas) em
`models/vision-detector/`. Ver [Gerando o ArchitectureDiagram
JSON](#gerando-o-architecturediagram-json-a-partir-de-um-diagrama) para o
formato de saída e como interpretar os campos `confidence`/`note`.

## Dataset

[`aws-icon-detector`](https://universe.roboflow.com/aws-icons/aws-icon-detector/browse?queryText=&pageSize=50&startingIndex=0&browseQuery=true) (Roboflow Universe).

## Por que colapsar em arquétipos?

O dataset `aws-icon-detector` tem **185 classes para 210 imagens** (~1 imagem por
classe). Treinar direto nas 185 classes não funciona. Colapsando em ~15 arquétipos
(`compute`, `database`, `storage`, `api_gateway`, `load_balancer`, ...), cada classe
passa a ter exemplos suficientes — e o arquétipo é exatamente a chave da base STRIDE.

## Passos (pipeline completo, do zero)

```bash
pip install ultralytics pyyaml

# 1. Baixe o dataset do Roboflow no formato "YOLOv8" -> pasta ./aws-icon-detector
#    https://universe.roboflow.com/aws-icons/aws-icon-detector/browse
#    (Universe > Dataset > Download > YOLOv8)

# 2. Colapse as 185 classes em arquétipos
python remap_labels.py --src ./aws-icon-detector --dst ./dataset_archetypes
#    -> Ele lista as classes ainda NÃO mapeadas. Cole-as em class_to_archetype.py
#       (defina o arquétipo de cada uma) e rode de novo até não sobrar nenhuma.

# 3. (opcional, mas recomendado) gere dados sinteticos via draw.io e junte aos
#    splits de dataset_archetypes/ -- ver secao "Dataset sintetico" abaixo.

# 4. Treine (ver tempo estimado abaixo -- GPU recomendada)
python train.py

# 5. Rode a inferência num diagrama de teste (ex.: a Figura 1 do enunciado)
python predict.py minha_arquitetura.png
```

## Dataset sintetico (draw.io)

`generate_synthetic_drawio.py` gera diagramas sinteticos renderizando o
proprio draw.io headless (mesmos icones AWS4, fontes e conectores que um
usuario veria montando um diagrama de verdade), com bounding boxes YOLO
derivadas direto da geometria do XML (sem anotacao manual). Isso ajuda
justamente porque a inferencia final roda sobre diagramas que os usuarios
desenham no draw.io — treinar com exemplos nesse mesmo estilo visual reduz
o gap entre treino e uso real, alem de aliviar o desbalanceamento de classes
do dataset do Roboflow.

Roda no HOST (nao no container Docker, ja que precisa do app Electron do
draw.io + display grafico headless), e **nao usa GPU** (e so renderizacao,
CPU-bound):

```bash
sudo snap install drawio
sudo apt-get install -y xvfb

python generate_synthetic_drawio.py --n 1800 --out dataset_synthetic_drawio
```

Tempo medido: **~20 minutos para 1800 diagramas** (varia com a CPU do host,
mas nao depende de GPU). Gera
`dataset_synthetic_drawio/{train,valid,test}/{images,labels}` + `data.yaml`,
na mesma convencao do `dataset_archetypes/`. Para combinar com o dataset
real, copie os arquivos de cada split de `dataset_synthetic_drawio/` para
dentro de `dataset_archetypes/` (mesmos nomes de arquetipo, mesmos splits)
antes de rodar `train.py`.

## Rodando via Docker

Não precisa instalar Python/ultralytics localmente. A partir da raiz do repositório
(onde está o `docker-compose.yml`):

```bash
# build da imagem
docker compose build vision-detector

# 1. Baixe o dataset do Roboflow e extraia em models/vision-detector/aws-icon-detector

# 2. Colapse as classes em arquétipos
docker compose run --rm vision-detector python remap_labels.py --src aws-icon-detector --dst dataset_archetypes

# 3. Treine
docker compose run --rm vision-detector python train.py

# 4. Rode a inferência (a imagem de entrada deve estar dentro de models/vision-detector/)
docker compose run --rm vision-detector python predict.py minha_arquitetura.png
```

Todos os artefatos (`aws-icon-detector/`, `dataset_archetypes/`, `runs/`,
`deteccao_saida.jpg`) são lidos/gravados diretamente em `models/vision-detector/`
no host, já que a pasta inteira é montada como volume dentro do container.

## Servidor HTTP (`api.py`) -- consumido pelo resto do projeto

Além dos scripts de linha de comando acima, `docker compose up vision-detector`
(comando default do container, ver `Dockerfile`) sobe um servidor FastAPI
próprio (`api.py`) que expõe a detecção via HTTP:

- `GET /health` — reporta se os pesos treinados estão presentes em disco.
- `POST /predict` — recebe uma imagem (`multipart/form-data`, campo `image`)
  e devolve o `ArchitectureDiagram` completo em JSON (mesmo formato do
  arquivo `*_architecture.json` gerado por `predict.py`).

No startup, se os pesos (`runs/detect/stride/weights/best.pt`) ainda não
existirem, `api.py` tenta baixá-los automaticamente do Hugging Face (ver
[Modelo e dataset no Hugging Face](#modelo-e-dataset-no-hugging-face) abaixo).
Se o download falhar (ex.: ambiente sem internet), os logs do container
mostram o comando `hf download ...` pra baixar manualmente — os endpoints
seguem de pé e reportam pesos ausentes em vez de derrubar o container.

É esse servidor que `extraction/service.py` (raiz do repo) chama via
`VISION_DETECTOR_URL` — ver `docs/development.md#extração-de-diagrama-vision-detector`
para como isso se encaixa no resto da API. Os scripts de treino/avaliação
continuam funcionando normalmente via `docker compose run --rm
vision-detector python <script>.py`, que sobrescreve esse comando default.

## Requisitos de hardware e tempo estimado

**Resumo:** treinar do zero é bem mais rápido com GPU (~30 min) do que sem
(~1 dia); **inferência** (`predict.py`, usar um modelo já treinado) é rápida
nos dois casos e não exige GPU.

| Etapa | Com GPU (ex.: RTX 5070) | Sem GPU (CPU) |
|---|---|---|
| Gerar dataset sintético (1800 diagramas) | ~20 min (não usa GPU mesmo com ela disponível) | ~20 min |
| Treinar (150 épocas, ~1600 imagens) | **~30 min** (medido) | **~1 dia** (medido: ~10 min/época em CPU de 16 núcleos — escala com o hardware, pode ser bem mais lento em notebook) |
| Inferência (`predict.py`, 1 imagem) | < 0.1 s | **~0.2 s** (medido, imgsz=1280) |

Ou seja: **sem GPU, pule o treino** e use os pesos já treinados (ver
[Modelo e dataset no Hugging Face](#modelo-e-dataset-no-hugging-face)) — só a
etapa de treino é impraticável em CPU, a inferência funciona bem.

### GPU (NVIDIA Blackwell, ex.: RTX 5070)

O `Dockerfile` já instala o build de torch com CUDA 12.8
(`torch==2.9.1+cu128` via `https://download.pytorch.org/whl/cu128`), necessário
porque GPUs Blackwell (sm_120) não são suportadas pelo torch que
`pip install ultralytics` puxaria por padrão — isso resultaria em
`RuntimeError: no kernel image is available for execution on the device`.
O pin é reaplicado logo depois de instalar o `ultralytics`, já que ele declara
sua própria faixa de versão de torch e o pip poderia trocar o build silenciosamente.

Pré-requisitos no host:
- Driver NVIDIA instalado
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
  configurado (`docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu22.04 nvidia-smi`
  deve funcionar)

O `docker-compose.yml` já reserva a GPU (`deploy.resources.reservations.devices`)
para o serviço `vision-detector`. Para confirmar que o container está enxergando
a GPU:

```bash
docker compose run --rm vision-detector python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

### Sem GPU (CPU)

Passo a passo para rodar em uma máquina sem GPU (ex.: notebook comum):

1. **Remova o bloco `deploy:`** do `docker-compose.yml` (o serviço
   `vision-detector`) — sem isso, `docker compose run` falha tentando reservar
   uma GPU que não existe.
2. **Troque o pin de torch no `Dockerfile`** pela versão CPU padrão do
   ultralytics: remova as duas linhas que instalam
   `torch==2.9.1+cu128 ... --index-url https://download.pytorch.org/whl/cu128`
   (o `pip install ultralytics` já traz um torch CPU-only funcional sozinho).
3. Rebuild: `docker compose build vision-detector`.
4. Para **inferência** (`predict.py`), nada mais muda — roda em ~0.2s por
   imagem, sem diferença prática de UX.
5. Para **treino** (`train.py`), funciona, mas é lento (ver tabela acima —
   ~1 dia para as 150 épocas default numa CPU de 16 núcleos, pode passar
   disso em hardware mais fraco). Recomendado: baixe os pesos já treinados do
   Hugging Face em vez de retreinar (ver seção abaixo), a menos que você
   precise mesmo re-treinar com dados novos.

## Modelo e dataset no Hugging Face

Os pesos treinados (`best.pt`) e o dataset completo (`dataset_archetypes/`,
Roboflow remapeado + dados sintéticos + anotações reais à mão) estão
publicados no Hugging Face Hub, para quem quiser usar o modelo sem rodar o
pipeline de treino inteiro:

- Modelo: [luisasousa/aws-architecture-vision-detector](https://huggingface.co/luisasousa/aws-architecture-vision-detector)
- Dataset: [luisasousa/aws-architecture-diagrams](https://huggingface.co/datasets/luisasousa/aws-architecture-diagrams)

```bash
pip install huggingface_hub
hf download luisasousa/aws-architecture-vision-detector best.pt --local-dir models/vision-detector/runs/detect/stride/weights/
hf download luisasousa/aws-architecture-diagrams --repo-type dataset --local-dir models/vision-detector/dataset_archetypes/
```

## Gerando o ArchitectureDiagram JSON a partir de um diagrama

```bash
# via Docker (imagem de entrada deve estar em models/vision-detector/)
docker compose run --rm vision-detector python predict.py minha_arquitetura.png

# ou direto no host, se tiver ultralytics/torch instalados
python predict.py minha_arquitetura.png
```

Isso salva `minha_arquitetura_architecture.json` (o `ArchitectureDiagram`
completo, contrato Pydantic definido em `extraction/schemas.py`) e
`deteccao_saida.jpg` (a mesma imagem com as caixas detectadas desenhadas,
útil pra conferir visualmente o que o modelo achou) na mesma pasta da
imagem de entrada. O terminal também imprime um resumo (componentes por
arquétipo, trust boundaries, data flows).

Estrutura do JSON gerado:

```jsonc
{
  "diagram_metadata": {
    "cloud_provider": "aws",
    "region": "sa-east-1",           // lido via OCR quando encontrado, senao null
    "extraction_confidence": "alta"  // "alta"/"média"/"baixa", baseado na confianca media das deteccoes
  },
  "trust_boundaries": [
    {
      "id": "tb1",
      "name": "VPC",                  // lido via OCR quando disponivel
      "type": "vpc",                  // sub-tipo do YOLO (vpc/region/availability_zone/...) ou "boundary" generico
      "parent": null,                 // id de outra trust_boundary (aninhamento, ex.: subnet dentro de VPC)
      "confidence": 0.91,
      "note": null                    // sinaliza problema (ex.: "rastreamento do retângulo falhou")
    }
  ],
  "components": [
    {
      "id": "c_compute_1",
      "name": "EC2 Instances",         // texto lido via OCR, ou "{Arquétipo em PT-BR} {n}" como fallback
      "aws_service": "EC2",            // vem da deteccao fina do YOLO ou de match do texto OCR contra nomes de servico AWS
      "element_type": "process",       // process/data_store/data_flow/external_entity (usado pelo STRIDE)
      "category": "compute",           // arquetipo (identificador em ingles, chave da base STRIDE)
      "trust_boundary": "tb1",         // id da trust_boundary mais interna que contem este componente
      "confidence": 0.87,
      "note": null
    }
  ],
  "data_flows": [
    {
      "id": "f1",
      "source": "c_compute_1",
      "destination": "c_database_1",
      "protocol": "desconhecido",      // lido via OCR perto da seta, ou "desconhecido" se nao achou
      "crosses_boundary": false,       // source e destination estao em trust_boundary diferentes?
      "confidence": 0.72,
      "note": null
    }
  ]
}
```

**Campos `confidence`/`note` (design HITL):** o sistema não afirma certeza
falsa — quando o OCR não lê um texto, ou o rastreamento do retângulo de uma
boundary falha, ou o texto lido não bate com nenhum serviço AWS conhecido,
o campo `note` sinaliza isso explicitamente (em vez de inventar um valor).
Use isso para priorizar o que revisar manualmente antes de alimentar a
modelagem STRIDE.

Para usar um checkpoint de pesos diferente do default
(`runs/detect/stride/weights/best.pt`), edite a constante `WEIGHTS` no topo
de `predict.py`.

## Arquivos

- `class_to_archetype.py` — mapa classe → arquétipo (chave dupla: treino + STRIDE)
- `remap_labels.py` — reescreve o dataset colapsando as classes
- `generate_synthetic_drawio.py` — gera dataset sintético via draw.io headless
- `train.py` — treino YOLOv8 com augmentation p/ dataset pequeno
- `predict.py` — detecta e monta o `ArchitectureDiagram` (containment de
  trust boundary, matching seta→componente, OCR best-effort); cada
  componente/flow/boundary carrega `confidence` (da detecção) e `note`
  (sinaliza quando OCR não achou texto ou o rastreamento do retângulo da
  boundary falhou) — usar para priorizar o que revisar no HITL.
- `eval_against_ground_truth.py` — acerto do detector (IoU de bounding boxes)
  contra 5 diagramas reais anotados à mão em `real_eval_holdout/ground_truth/`
  (fonte de verdade autoritativa deste projeto — nunca usados em treino)
- `eval_diagram_level.py` — acerto do `ArchitectureDiagram` final contra um
  gabarito anotado à mão (precisa de `expected_*.json`, ver docstring)
- `tests/test_predict_geometry.py` — testes unitários das heurísticas
  geométricas (containment, matching seta→componente, etc.)

### Nota: pasta `extraction/` vazia neste diretório

Se você já rodou `docker compose run vision-detector` alguma vez, vai notar
uma pasta `models/vision-detector/extraction/` vazia, dona `root`. Isso é o
Docker criando o mount point pro bind-mount `./extraction:/app/extraction`
declarado no `docker-compose.yml` (`/app` aqui é o próprio
`models/vision-detector`, montado no host) — não é um pacote Python real,
é só o ponto de montagem. `predict.py` já lida com isso (checa
`extraction/schemas.py`, não só a pasta, antes de decidir onde está a raiz
do repo); pode deixar essa pasta vazia aí, ela não atrapalha nada rodando
direto no host.

## Para a documentação/vídeo do hackathon

Registre: distribuição de instâncias por arquétipo (antes/depois do colapso),
curvas de treino (`results.png`), matriz de confusão, mAP50 e mAP50-95, e a
inferência rodada **na Figura 1 do enunciado**. Deixe claro que arquétipos
frequentes (compute, database, storage, api_gateway, load_balancer, external_actor)
são os confiáveis; os raros ficam limitados pelo tamanho do dataset — e proponha
como trabalho futuro ampliar o dataset com diagramas gerados no draw.io.

Métricas de referência atuais:

- **mAP50=0.85, mAP50-95=0.80** (saída de `train.py` no split `dataset_archetypes/test`
  — mistura real+sintético, sinal mais fraco, é a métrica padrão do YOLO)
- **boundary F1≈0.57, componente F1≈0.81 (acurácia de categoria≈0.79 dado
  localização correta), arrowhead F1≈0.54** (via `eval_against_ground_truth.py`,
  5 imagens reais anotadas à mão, nunca usadas em treino — a fonte de verdade
  mais confiável deste projeto, ver `real_eval_holdout/ground_truth/`)
