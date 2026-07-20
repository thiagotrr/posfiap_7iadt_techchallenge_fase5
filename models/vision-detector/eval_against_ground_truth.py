"""
Score the trained YOLO model against hand-annotated ground truth in
real_eval_holdout/ground_truth/annotations.json.

Matches detections to ground-truth boxes via IoU (greedy, highest-IoU-first,
one-to-one), per class group (boundary / component / arrowhead). For
"component" also reports how many IoU-matches also got the right category
(archetype), since a detection can localize correctly but classify wrong.

Uso:
    python eval_against_ground_truth.py [--iou 0.5] [--conf 0.25] [--imgsz 1280]
"""

import argparse
import json
from pathlib import Path

from ultralytics import YOLO

import predict as P

WEIGHTS = "runs/detect/stride/weights/best.pt"
GT_PATH = "real_eval_holdout/ground_truth/annotations.json"
IMAGE_ROOT = {
    "figure1backup": "real_detection_data",
    "oracleebs": "real_eval_holdout",
    "figura1": "real_eval_holdout",
    "eks": "real_eval_holdout",
    "moderndata": "real_eval_holdout",
}
BOUNDARY_CLASS = "boundary"
ARROWHEAD_CLASS = "arrowhead"
# ground truth so conhece "boundary" generico (nao os sub-tipos vpc/region/
# etc., ver class_to_archetype.py::BOUNDARY_SUBTYPES) -- agrupa qualquer
# sub-tipo detectado como "boundary" tambem, senao contaria como
# "component" e corromperia a comparacao.
BOUNDARY_CLASSES = P.BOUNDARY_CLASSES


def iou(a, b):
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    iw, ih = max(0, ix1 - ix0), max(0, iy1 - iy0)
    inter = iw * ih
    area_a = max(0, ax1 - ax0) * max(0, ay1 - ay0)
    area_b = max(0, bx1 - bx0) * max(0, by1 - by0)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def group_of(cls_name):
    if cls_name in BOUNDARY_CLASSES:
        return "boundary"
    if cls_name == ARROWHEAD_CLASS:
        return "arrowhead"
    return "component"


def match(preds, gts, iou_thresh):
    """Greedy one-to-one IoU matching. preds/gts: list of dict(box=(x0,y0,x1,y1), category=...).
    Returns (matched_pairs, unmatched_preds, unmatched_gts)."""
    pairs = []
    used_gt = set()
    # sort preds by confidence desc if present, else stable order
    order = sorted(range(len(preds)), key=lambda i: -preds[i].get("conf", 0))
    for pi in order:
        best_j, best_iou = None, 0.0
        for j, g in enumerate(gts):
            if j in used_gt:
                continue
            v = iou(preds[pi]["box"], g["box"])
            if v > best_iou:
                best_iou, best_j = v, j
        if best_j is not None and best_iou >= iou_thresh:
            used_gt.add(best_j)
            pairs.append((pi, best_j, best_iou))
    matched_preds = {p for p, _, _ in pairs}
    matched_gts = {g for _, g, _ in pairs}
    unmatched_preds = [i for i in range(len(preds)) if i not in matched_preds]
    unmatched_gts = [j for j in range(len(gts)) if j not in matched_gts]
    return pairs, unmatched_preds, unmatched_gts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iou", type=float, default=0.5)
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--imgsz", type=int, default=1280)
    args = ap.parse_args()

    gt_all = json.loads(Path(GT_PATH).read_text())
    model = YOLO(WEIGHTS)

    totals = {"boundary": [0, 0, 0], "component": [0, 0, 0], "arrowhead": [0, 0, 0]}  # tp, fp, fn
    category_correct, category_total = 0, 0

    for key, entry in gt_all.items():
        img_path = str(Path(IMAGE_ROOT[key]) / entry["file"])
        result = model.predict(source=img_path, conf=args.conf, imgsz=args.imgsz, verbose=False)[0]
        names = result.names

        preds_by_group = {"boundary": [], "component": [], "arrowhead": []}
        boundary_boxes_raw = []  # list[P.Det], antes do dedup/rastreamento -- precisa pra tracing
        component_boxes, arrowhead_boxes = [], []
        for box, cls_id, conf in zip(
            result.boxes.xyxy.tolist(), result.boxes.cls.tolist(), result.boxes.conf.tolist()
        ):
            cname = names[int(cls_id)]
            g = group_of(cname)
            if g == "boundary":
                boundary_boxes_raw.append(P.Det(cls_name=cname, box=tuple(box), conf=conf))
            elif g == "arrowhead":
                arrowhead_boxes.append(tuple(box))
            else:
                component_boxes.append(tuple(box))
                # ground truth so tem categoria em nivel de ARQUETIPO -- rola
                # pra arquetipo antes de comparar (P._category_of), senao um
                # acerto fino de verdade (ex.: previu "RDS", GT diz
                # "database") contaria como erro.
                preds_by_group["component"].append(
                    {"box": tuple(box), "category": P._category_of(cname), "conf": conf}
                )
        for box in arrowhead_boxes:
            preds_by_group["arrowhead"].append({"box": box, "category": None, "conf": 1.0})

        # boundary: dedup classe-agnostica primeiro (mesma logica de
        # build_trust_boundaries -- sem isso, "boundary" e "vpc" (ou
        # qualquer combinacao de sub-tipo) disparando quase na mesma regiao
        # sobrevivem os dois ao NMS por classe do YOLO e um vira falso-
        # positivo espurio aqui, mesmo sendo a MESMA deteccao real). Depois,
        # marcador de canto -> retangulo real via rastreamento classico, com
        # a MESMA regra de preferencia que build_trust_boundaries usa (caixa
        # bruta por padrao, so troca pelo rastreamento quando ele concorda
        # o bastante) -- antes este script sempre preferia o rastreamento
        # quando disponivel, divergindo da logica real de predict.py.
        exclude_for_tracing = component_boxes + arrowhead_boxes
        for d in P._dedup_boundary_dets(boundary_boxes_raw):
            traced = P._trace_boundary_box(result.orig_img, d.box, exclude_for_tracing)
            use_traced = traced is not None and P._iou(traced, d.box) >= 0.5
            box = traced if use_traced else d.box
            preds_by_group["boundary"].append({"box": box, "category": None, "conf": d.conf})

        gts_by_group = {"boundary": [], "component": [], "arrowhead": []}
        for b in entry["boxes"]:
            g = group_of(b["cls"])
            gts_by_group[g].append({"box": tuple(b["box"]), "category": b["category"]})

        print(f"\n=== {key} ({entry['file']}) ===")
        for g in ("boundary", "component", "arrowhead"):
            preds, gts = preds_by_group[g], gts_by_group[g]
            pairs, unmatched_preds, unmatched_gts = match(preds, gts, args.iou)
            tp, fp, fn = len(pairs), len(unmatched_preds), len(unmatched_gts)
            totals[g][0] += tp
            totals[g][1] += fp
            totals[g][2] += fn
            if g == "component":
                for pi, gj, _ in pairs:
                    category_total += 1
                    if preds[pi]["category"] == gts[gj]["category"]:
                        category_correct += 1
            prec = tp / (tp + fp) if (tp + fp) else float("nan")
            rec = tp / (tp + fn) if (tp + fn) else float("nan")
            print(f"  {g:10s} gt={len(gts):3d} pred={len(preds):3d}  tp={tp:3d} fp={fp:3d} fn={fn:3d}  "
                  f"precision={prec:.2f} recall={rec:.2f}")

    print("\n=== TOTAL (all {} images, IoU>={:.1f}) ===".format(len(gt_all), args.iou))
    for g in ("boundary", "component", "arrowhead"):
        tp, fp, fn = totals[g]
        prec = tp / (tp + fp) if (tp + fp) else float("nan")
        rec = tp / (tp + fn) if (tp + fn) else float("nan")
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) and prec == prec and rec == rec and (prec + rec) > 0 else float("nan")
        print(f"  {g:10s} tp={tp:3d} fp={fp:3d} fn={fn:3d}  precision={prec:.2f} recall={rec:.2f} f1={f1:.2f}")

    if category_total:
        print(f"\n  component category accuracy (given correct localization): "
              f"{category_correct}/{category_total} = {category_correct/category_total:.2f}")


if __name__ == "__main__":
    main()
