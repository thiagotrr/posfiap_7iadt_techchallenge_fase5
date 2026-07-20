"""
Treino do detector de arquetipos de arquitetura (YOLOv8).

pip install ultralytics

Uso:
    python train.py

Notas para o dataset pequeno (210 imgs):
  - yolov8s.pt e um bom equilibrio. Se overfittar, teste yolov8n.pt.
  - augmentation forte ajuda MUITO aqui. Como icones nao tem orientacao fixa
    em diagramas, mas texto/setas tem, evite flip vertical.
  - patience=25 faz early-stopping quando a val para de melhorar.
  - Depois do treino, olhe runs/detect/stride/results.png e a matriz de confusao
    para saber QUAIS arquetipos o modelo realmente aprendeu (os frequentes:
    compute, database, storage, api_gateway, load_balancer, external_actor).
"""

import datetime
import shutil
from pathlib import Path

from ultralytics import YOLO

DATA = "dataset_archetypes/data.yaml"
WEIGHTS_OUT = Path("runs/detect/stride/weights/best.pt")
CHECKPOINTS_DIR = Path("runs/detect/checkpoints")

# Arquiva o checkpoint atual ANTES de sobrescrever (exist_ok=True abaixo
# apaga o run anterior). Sem isso, um retreino que regride silenciosamente
# em algum diagrama real nao tem como ser revertido -- ja aconteceu uma vez
# neste projeto (ver git log / conversa: "boundary-collapse" regression).
if WEIGHTS_OUT.exists():
    CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = CHECKPOINTS_DIR / f"best_{ts}_pretrain.pt"
    shutil.copy2(WEIGHTS_OUT, dest)
    print(f"Checkpoint anterior arquivado em {dest}")

model = YOLO("yolov8s.pt")  # pesos pre-treinados no COCO (transfer learning)

model.train(
    data=DATA,
    epochs=150,
    imgsz=640,
    batch=16,
    patience=25,
    name="stride",
    exist_ok=True,  # sobrescreve runs/detect/stride/ em vez de criar stride-2, stride-3...
    # (predict.py aponta pra um caminho fixo, nao pro run mais recente)
    # --- augmentation (importante para dataset pequeno) ---
    hsv_h=0.015, hsv_s=0.7, hsv_v=0.4,
    degrees=5,          # leve rotacao
    translate=0.1,
    scale=0.5,
    fliplr=0.5,         # flip horizontal ok
    flipud=0.0,         # NAO flipar na vertical (icones/setas ficam sem sentido)
    mosaic=1.0,
    mixup=0.1,
    # Tentativa: mosaic=0.5 + box=10.0 (menos mosaic, mais peso na loss de
    # bbox regression), na teoria pra ajudar boundary (objeto grande/esparso,
    # problema de localizacao). Piorou tudo na pratica -- boundary F1 0.49
    # -> 0.36, component F1 0.74 -> 0.66 (ver eval_against_ground_truth.py) --
    # revertido. Mosaic parece estar puxando peso como REGULARIZADOR nesse
    # dataset pequeno (~1600 imagens), nao so como distorcao de escala; tirar
    # ele parece ter custado mais do que ajudou a localizacao de boundary.
)

# Avaliacao no split de teste
metrics = model.val(split="test")
print("mAP50-95:", metrics.box.map)
print("mAP50:", metrics.box.map50)
