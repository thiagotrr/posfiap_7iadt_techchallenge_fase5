"""
Colapsa as 185 classes do dataset aws-icon-detector em ~15 arquetipos.

Le um export YOLOv8 do Roboflow e escreve um NOVO dataset com as classes
remapeadas. Isso multiplica os exemplos por classe e torna o treino viavel.

Uso:
    python remap_labels.py --src ./aws-icon-detector --dst ./dataset_archetypes

Passo a passo antes de rodar:
    1) No Roboflow, exporte o dataset no formato "YOLOv8" (baixa uma pasta com
       data.yaml, train/, valid/, test/).
    2) Aponte --src para essa pasta.
    3) Rode. O script AVISA quais classes do data.yaml nao estao no mapeamento
       (as ~65 que a pagina nao mostrava). Adicione-as em class_to_archetype.py
       e rode de novo.

Arquetipos em EXCLUDE sao descartados dos rotulos (nao viram objeto de deteccao).
"""

import argparse
import random
import shutil
from pathlib import Path

import yaml  # pip install pyyaml

from class_to_archetype import DETECTION_CLASSES, detection_class_of

# Arquetipos que NAO queremos que o detector aprenda como objeto.
# 'other' e ruido/generico (Table, Container, Marketplace, etc.) -- inclui
# as classes Roboflow "VPC"/"Availability Zone"/"Public Subnet"/"Private
# Subnet"/"Region"/"aws" (continuam mapeadas pra "other" mesmo com os
# sub-tipos de boundary novos: sao o pictograma pequeno nesse dataset, nao
# o retangulo -- promove-las pro sub-tipo reintroduziria o mesmo bug de
# caixa-de-icone-vs-caixa-de-retangulo ja corrigido pra "boundary", ver
# comentario grande em class_to_archetype.py::BOUNDARY_SUBTYPES).
# 'boundary' e os sub-tipos (aws_cloud/vpc/region/availability_zone/
# public_subnet/private_subnet) sao classes de deteccao normais, mas vem
# EXCLUSIVAMENTE do dataset sintetico (generate_synthetic_drawio.py) -- o
# Roboflow nao tem o retangulo anotado, so o pictograma.
EXCLUDE = {"other"}


def load_names(data_yaml: Path) -> list[str]:
    data = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    names = data["names"]
    if isinstance(names, dict):  # {0: 'a', 1: 'b'} -> ['a','b']
        names = [names[i] for i in sorted(names)]
    return names


def build_index_map(old_names: list[str]):
    """old_id -> new_id (ou None se descartado), usando a ORDEM FIXA de
    DETECTION_CLASSES (nao por presenca) -- assim os ids de classe batem com
    dataset_synthetic_drawio/ ao fazer merge dos splits (ver README). Tambem
    retorna quais arquetipos deste dataset tem pelo menos 1 exemplo (so
    informativo) e a lista de classes originais nao mapeadas."""
    new_id_of = {arch: i for i, arch in enumerate(DETECTION_CLASSES)}
    present, unmapped = set(), []
    for name in old_names:
        cls = detection_class_of(name)
        if cls is None:
            unmapped.append(name)
        elif cls not in EXCLUDE:
            present.add(cls)

    old_to_new = {}
    for old_id, name in enumerate(old_names):
        cls = detection_class_of(name)
        old_to_new[old_id] = new_id_of.get(cls) if cls not in EXCLUDE else None
    return old_to_new, sorted(present), unmapped


def remap_split(src_split: Path, dst_split: Path, old_to_new: dict):
    (dst_split / "images").mkdir(parents=True, exist_ok=True)
    (dst_split / "labels").mkdir(parents=True, exist_ok=True)

    img_src, lbl_src = src_split / "images", src_split / "labels"
    if not img_src.exists():
        return 0

    for img in img_src.iterdir():
        shutil.copy2(img, dst_split / "images" / img.name)

    for lbl in lbl_src.glob("*.txt"):
        out_lines = []
        for line in lbl.read_text().splitlines():
            parts = line.split()
            if not parts:
                continue
            old_id = int(parts[0])
            new_id = old_to_new.get(old_id)
            if new_id is None:  # classe descartada
                continue
            out_lines.append(" ".join([str(new_id), *parts[1:]]))
        (dst_split / "labels" / lbl.name).write_text("\n".join(out_lines))
    return 1


def ensure_val_split(dst: Path, frac: float = 0.15, seed: int = 42):
    """Alguns exports do Roboflow vem sem pasta 'valid' (tudo em train/test).
    YOLO precisa de um val set nao-vazio a cada epoca, entao se valid estiver
    vazio, tira uma fatia determinística de train para virar valid."""
    train_imgs = sorted((dst / "train" / "images").glob("*"))
    valid_imgs = list((dst / "valid" / "images").glob("*"))
    if valid_imgs or not train_imgs:
        return

    rng = random.Random(seed)
    rng.shuffle(train_imgs)
    n_val = max(1, round(len(train_imgs) * frac))
    for img in train_imgs[:n_val]:
        lbl = dst / "train" / "labels" / (img.stem + ".txt")
        shutil.move(str(img), dst / "valid" / "images" / img.name)
        if lbl.exists():
            shutil.move(str(lbl), dst / "valid" / "labels" / lbl.name)
    print(f"AVISO: 'valid' veio vazio do export. Movidas {n_val} imagens de train/ para valid/ (frac={frac}).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="pasta do export YOLOv8 do Roboflow")
    ap.add_argument("--dst", required=True, help="pasta de saida")
    args = ap.parse_args()

    src, dst = Path(args.src), Path(args.dst)
    old_names = load_names(src / "data.yaml")
    old_to_new, used, unmapped = build_index_map(old_names)

    if unmapped:
        print("=" * 60)
        print(f"ATENCAO: {len(unmapped)} classes NAO estao em class_to_archetype.py.")
        print("Elas serao DESCARTADAS. Adicione-as ao mapeamento e rode de novo:")
        for n in unmapped:
            print(f'    "{n}": "?",')
        print("=" * 60)

    for split in ("train", "valid", "test"):
        remap_split(src / split, dst / split, old_to_new)

    ensure_val_split(dst)

    # nc/names sempre usam a lista FIXA (DETECTION_CLASSES), nao so as
    # classes presentes neste dataset -- classes sem exemplo aqui (ex.:
    # "arrowhead", que so o gerador sintetico produz) ainda precisam manter
    # o mesmo id ao fazer merge com dataset_synthetic_drawio/.
    new_data = {
        "train": "train/images",
        "val": "valid/images",
        "test": "test/images",
        "nc": len(DETECTION_CLASSES),
        "names": DETECTION_CLASSES,
    }
    (dst / "data.yaml").write_text(yaml.safe_dump(new_data, sort_keys=False))

    missing = [a for a in DETECTION_CLASSES if a not in used]
    print(f"\nOK. {len(old_names)} classes -> {len(used)}/{len(DETECTION_CLASSES)} arquetipos com exemplo:")
    for a in used:
        print(f"  {DETECTION_CLASSES.index(a)}: {a}")
    if missing:
        print(f"Sem exemplo neste dataset (ok, id reservado mesmo assim): {missing}")
    print(f"\nDataset remapeado em: {dst/'data.yaml'}")


if __name__ == "__main__":
    main()
