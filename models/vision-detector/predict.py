"""
Inferencia: recebe uma imagem de arquitetura e devolve um ArchitectureDiagram
completo (componentes, trust boundaries e data flows), que alimenta a etapa
de modelagem STRIDE.

Uso:
    python predict.py caminho/para/diagrama.png
"""

import difflib
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

try:
    import pytesseract
except ImportError:  # OCR e best-effort: sem tesseract, name/type/protocol viram placeholder
    pytesseract = None

# Acha o diretorio que contem extraction/, subindo a partir daqui: e /app
# dentro do container (montado em /app/extraction) ou a raiz do repo se
# rodado direto do host (models/vision-detector/../../extraction).
#
# Checa schemas.py, nao so a pasta: docker-compose monta ./extraction:/app/extraction
# dentro de ./models/vision-detector:/app (ver docker-compose.yml), e o Docker
# cria o mount point models/vision-detector/extraction/ vazio no HOST pra isso.
# Rodando fora do container, essa pasta vazia sobrevive e "e_dir() == True"
# faria o loop parar aqui (achando um pacote extraction vazio, sem schemas.py)
# em vez de subir ate a raiz do repo.
_here = Path(__file__).resolve().parent
for _candidate in (_here, *_here.parents):
    if (_candidate / "extraction" / "schemas.py").is_file():
        if str(_candidate) not in sys.path:
            sys.path.insert(0, str(_candidate))
        break

from extraction.schemas import ArchitectureDiagram  # noqa: E402
from class_to_archetype import (  # noqa: E402
    ARCHETYPE_LABEL_PT, ARCHETYPES, AWS_SERVICE_NAMES, BOUNDARY_SUBTYPES, archetype_of,
)

WEIGHTS = "runs/detect/stride/weights/best.pt"
CONF = 0.25  # limiar de confianca; suba para menos falsos-positivos
# 1280 (vs o default 640) porque diagramas reais costumam ter bastante
# espaco em branco ao redor do conteudo (a diferenca de crop apertado dos
# sinteticos), o que encolhe icones/setas na hora do resize -- setas
# (a classe menor de todas) sao as mais sensiveis a isso. Testado na
# Figura 1 do enunciado: confianca da melhor deteccao de seta foi de 0.13
# (abaixo do limiar) para 0.76 so com essa mudanca, sem retreinar.
IMGSZ = 1280

BOUNDARY_CLASS = "boundary"  # generico (sem sub-tipo identificado)
# Sub-tipos de boundary (vpc/region/availability_zone/.../aws_cloud, ver
# class_to_archetype.py) SAO boundary tambem pra fins de filtragem
# component_dets vs. boundary_dets -- so o generico "boundary" continua
# usado como fallback de TYPE quando a deteccao nao e especifica.
BOUNDARY_CLASSES = {BOUNDARY_CLASS, *BOUNDARY_SUBTYPES}
ARROWHEAD_CLASS = "arrowhead"

# element_type do STRIDE por arquetipo. Nao listados caem em "process" (a
# maioria dos servicos AWS e algo que processa/media, nao um deposito de
# dados nem um ator externo).
ELEMENT_TYPE_OF = {
    "external_actor": "external_entity",
    "database": "data_store",
    "storage": "data_store",
    "messaging_eventing": "data_store",
}
DEFAULT_ELEMENT_TYPE = "process"


def _category_of(cls_name):
    """Rollup da classe de deteccao (arquetipo direto, ex. "compute", OU
    servico especifico promovido, ex. "RDS") pro ARQUETIPO usado em
    `category`/STRIDE/ELEMENT_TYPE_OF -- esses continuam so conhecendo
    arquetipo, nao os ~28 servicos especificos novos (ver class_to_
    archetype.py::FINE_GRAINED_SERVICES)."""
    if cls_name in ARCHETYPES:
        return cls_name
    return archetype_of(cls_name) or cls_name


@dataclass
class Det:
    cls_name: str
    box: tuple  # (x0, y0, x1, y1) em pixels
    conf: float


# --------------------------------------------------------------------------
# geometria
# --------------------------------------------------------------------------

def _center(box):
    x0, y0, x1, y1 = box
    return (x0 + x1) / 2, (y0 + y1) / 2


def _area(box):
    x0, y0, x1, y1 = box
    return max(0, x1 - x0) * max(0, y1 - y0)


def _dist(p, q):
    return ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5


def _contains(outer, inner, tol=4):
    ox0, oy0, ox1, oy1 = outer
    ix0, iy0, ix1, iy1 = inner
    return ox0 - tol <= ix0 and oy0 - tol <= iy0 and ix1 <= ox1 + tol and iy1 <= oy1 + tol


def _iou(a, b):
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    iw, ih = max(0.0, ix1 - ix0), max(0.0, iy1 - iy0)
    inter = iw * ih
    union = _area(a) + _area(b) - inter
    return inter / union if union > 0 else 0.0


def _dedup_boundary_dets(dets, iou_thresh=0.5):
    """NMS CLASSE-AGNOSTICA entre os detects de fronteira (generico
    "boundary" + os 6 sub-tipos, ver BOUNDARY_CLASSES) -- o NMS padrao do
    YOLO so suprime duplicatas DENTRO da mesma classe. Se o modelo dispara
    tanto "boundary" quanto "vpc" (ou qualquer combinacao de sub-tipos) pra
    praticamente a mesma regiao, as duas sobrevivem ao NMS e uma vira falso-
    positivo na comparacao com o ground truth (que so tem 1 caixa por regiao
    real) -- investigado via eval_against_ground_truth.py: precisao de
    boundary caindo (mais falso-positivo) mesmo com recall subindo depois do
    retreino, com deteccoes de classes diferentes se sobrepondo quase 100%
    na mesma regiao real. Mantem so a de maior confianca por cluster."""
    order = sorted(range(len(dets)), key=lambda i: -dets[i].conf)
    kept = []
    for i in order:
        if any(_iou(dets[i].box, dets[j].box) >= iou_thresh for j in kept):
            continue
        kept.append(i)
    return [dets[i] for i in kept]


def _box_point_dist(box, point):
    """Distancia do ponto ate a BORDA do box (0 se o ponto esta dentro).
    Mais precisa que distancia ao centro para casar arrowhead -> componente:
    com distancia ao centro, um componente grande "rouba" pontos que na
    verdade estao coladinhos na borda de um componente vizinho menor."""
    x0, y0, x1, y1 = box
    px, py = point
    dx = max(x0 - px, 0.0, px - x1)
    dy = max(y0 - py, 0.0, py - y1)
    return (dx ** 2 + dy ** 2) ** 0.5


def _nearest_component(point, components):
    if not components:
        return None
    return min(components, key=lambda c: _box_point_dist(c["box"], point))


# --------------------------------------------------------------------------
# OCR (best-effort: sem pytesseract/tesseract, cai em placeholder generico)
# --------------------------------------------------------------------------

def _ocr_text(image, box, pad_x=0, pad_y=0, psm=7, upscale=1):
    if pytesseract is None:
        return ""
    h, w = image.shape[:2]
    x0, y0, x1, y1 = [int(v) for v in box]
    x0, y0 = max(0, x0 - pad_x), max(0, y0 - pad_y)
    x1, y1 = min(w, x1 + pad_x), min(h, y1 + pad_y)
    crop = image[y0:y1, x0:x1]
    if crop.size == 0:
        return ""
    if upscale > 1:
        crop = cv2.resize(crop, None, fx=upscale, fy=upscale, interpolation=cv2.INTER_CUBIC)
    try:
        text = pytesseract.image_to_string(crop, config=f"--psm {psm}").strip()
    except Exception:
        return ""
    # psm 6 (usado pro rotulo de componente, ver _ocr_component_label) trata
    # o crop como bloco de texto -- se o crop nao tem texto de verdade (ex.:
    # so uma linha tracejada/fundo, caso do crop pequeno de _ocr_flow_
    # protocol), ele alucina "texto" a partir do ruido: string longa, cheia
    # de quebra de linha e pontuacao solta, sem letra de verdade. Descarta
    # esse caso em vez de devolver lixo (ex.: virou o "protocol" de um data
    # flow que nao tinha nenhum texto legivel perto da seta).
    alnum = sum(c.isalnum() for c in text)
    if len(text) > 15 and alnum / max(1, len(text)) < 0.4:
        return ""
    return text


def _ocr_boundary_label(image, box):
    """Le o rotulo no canto superior-esquerdo da caixa (mesma posicao onde o
    gerador sintetico desenha o texto: verticalAlign=top;align=left).
    Retorna tambem se o OCR efetivamente achou texto, pra sinalizar (via
    `note`, em build_trust_boundaries) que name/type sao placeholder."""
    x0, y0, x1, y1 = box
    crop_w = max(20, min(int(0.6 * (x1 - x0)), 240))
    crop_h = max(14, min(int(0.3 * (y1 - y0)), 40))
    text = _ocr_text(image, (x0, y0, x0 + crop_w, y0 + crop_h))
    name = text if text else "boundary"
    low = text.lower()
    if "vpc" in low:
        btype = "vpc"
    elif "subnet" in low:
        btype = "subnet"
    elif "zone" in low or " az" in low:
        btype = "availability_zone"
    elif "region" in low:
        btype = "region"
    elif "security" in low:
        btype = "security_group"
    else:
        btype = "boundary"
    return name, btype, bool(text)


_OCR_STRIP_CHARS = "-—_=|~*.,;:!?[]{}\"'“”‘’"


def _clean_ocr_text(text):
    """Limpa ruido tipico do OCR num crop pequeno/multi-linha: colapsa
    espaco/quebra-de-linha e descarta TOKENS que sao so pontuacao/simbolo
    (ex.: "——", "||", ")" solto) ou letras isoladas de 1-2 chars minusculas
    (ex.: "S", "I", "l", "ee", "ue" -- quase sempre ruido, um rotulo de
    servico de verdade nao tem "palavra" assim tao curta). NAO tenta
    corrigir erro de LEITURA de caractere (ex.: "Amazoa" por "Amazon") --
    so formatacao/ruido estrutural, que e o que sobra depois do psm 6 +
    upscale de _ocr_text ainda "alucinar" pontuacao solta em volta do texto
    de verdade. Mantem parenteses ("(Secondary)", "(memcached)") porque sao
    qualificador de instancia de verdade no estilo do diagrama de
    referencia, nao ruido."""
    if not text:
        return ""
    cleaned = []
    for tok in text.split():
        stripped = tok.strip(_OCR_STRIP_CHARS)
        if not stripped or not any(c.isalnum() for c in stripped):
            continue
        if stripped.isalpha() and (len(stripped) == 1 or (len(stripped) == 2 and stripped.islower())):
            continue
        cleaned.append(stripped)
    return " ".join(cleaned)


def _ocr_component_label(image, box):
    """Le o rotulo abaixo do icone -- mesma posicao onde o gerador sintetico
    desenha (verticalLabelPosition=bottom;align=center em STYLE_TMPL, ver
    generate_synthetic_drawio.py) e convencao tambem usada pelos icones
    oficiais AWS4 em diagramas reais. Cropa mais LARGO que o proprio icone
    (pad_x): o rotulo tipicamente estoura a largura do icone quadrado pros
    dois lados (ex.: "Elastic Load Balancer" e bem mais largo que o icone),
    igual ja fazia _ocr_boundary_label pro rotulo de uma boundary."""
    x0, y0, x1, y1 = box
    icon_w, icon_h = x1 - x0, y1 - y0
    pad_x = int(icon_w * 0.8)
    # antes cortava em 34px no maximo -- suficiente pra 1 linha, mas
    # rotulos reais de componente costumam quebrar em 2-3 linhas (ver
    # _ocr_text). 1.5x a altura do icone, ate 90px, da folga pra isso.
    crop_h = max(24, min(int(1.5 * icon_h), 90))
    # psm 6 (bloco multi-linha) + upscale 3x: diferente de _ocr_boundary_
    # label/_ocr_flow_protocol (crop pequeno, quase sempre so 1 linha ou
    # sem texto nenhum -- psm 6 + upscale ali alucinava "texto" a partir de
    # ruido/linha tracejada, ver _ocr_text). Rotulo de componente e maior
    # e sempre tem texto de verdade por baixo do icone, entao vale o custo.
    raw = _ocr_text(image, (x0, y1, x1, y1 + crop_h), pad_x=pad_x, psm=6, upscale=3)
    return _clean_ocr_text(raw)


def _normalize_for_match(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _match_aws_service(text):
    """Casa o texto lido via OCR contra AWS_SERVICE_NAMES (ver
    class_to_archetype.py). Retorna None se nao ha texto ou nenhum candidato
    bate com confianca suficiente -- preenchimento de aws_service e
    best-effort, igual ao resto do pipeline de OCR deste modulo; nao inventa
    servico quando incerto."""
    if not text:
        return None
    # diagramas reais costumam prefixar com "Amazon"/"AWS" (ver Figura 1 do
    # enunciado: "Amazon RDS", "AWS Lambda"), que nao faz parte do nome em
    # class_to_archetype.py -- tenta com e sem o prefixo.
    stripped = re.sub(r"^(amazon|aws)\s+", "", text.strip(), flags=re.IGNORECASE)
    for candidate in (stripped, text.strip()):
        if not candidate:
            continue
        matches = difflib.get_close_matches(candidate, AWS_SERVICE_NAMES, n=1, cutoff=0.72)
        if matches:
            return matches[0]

    # rotulos reais costumam ter palavras extras em volta do nome do servico
    # (ex.: "DynamoDB Tables", "SNS Notifications", "S3 Static Website") --
    # o fuzzy match acima compara a STRING INTEIRA e falha quando o texto
    # extra dilui a razao de similaridade. Fallback: compara JANELAS de 1-3
    # palavras CONSECUTIVAS do texto (normalizadas, sem espaco/case) contra
    # os nomes de servico tambem normalizados, exigindo IGUALDADE exata da
    # janela -- pega tanto "DynamoDB" (1 palavra no OCR) quanto "Dynamo DB"
    # (2 palavras no nome cadastrado) quanto o inverso. Comparar por janela
    # de palavra (nao substring livre no texto todo colado) evita
    # falso-positivo tipo "EBS" "achando" dentro de "webSite" (web-S-ite).
    words = re.findall(r"[a-zA-Z0-9]+", stripped) or re.findall(r"[a-zA-Z0-9]+", text)
    if not words:
        return None
    normalized_candidates = {_normalize_for_match(name): name for name in AWS_SERVICE_NAMES}
    best = None
    for start in range(len(words)):
        acc = ""
        for end in range(start, min(start + 3, len(words))):
            acc += words[end].lower()
            norm = _normalize_for_match(acc)
            if len(norm) >= 2 and norm in normalized_candidates:
                name = normalized_candidates[norm]
                if best is None or len(norm) > len(_normalize_for_match(best)):
                    best = name
    return best


def _ocr_flow_protocol(image, tip, far_point):
    if far_point is None:
        return None
    mx, my = (tip[0] + far_point[0]) / 2, (tip[1] + far_point[1]) / 2
    text = _ocr_text(image, (mx - 60, my - 20, mx + 60, my + 20))
    return text or None


# --------------------------------------------------------------------------
# trust boundaries: containment -> nesting, componente -> boundary mais interna
#
# O YOLO so consegue localizar de forma confiavel o ICONE de canto da
# boundary (~24x24px, fixo), nao o retangulo inteiro em si -- o retangulo
# varia demais de tamanho pra regressao direta aprender (ver
# eval_against_ground_truth.py e a investigacao que levou a essa mudanca:
# 3 rodadas de retraining tentando corrigir via dado sintetico so ajudaram
# parcialmente). Em vez de confiar na caixa prevista pelo YOLO, ela e tratada
# como um MARCADOR DE CANTO: a partir dali, rastreia-se a linha da borda de
# verdade com CV classica (mesmo padrao ja usado pra setas em
# build_data_flows) pra achar o retangulo real.
# --------------------------------------------------------------------------

def _dominant_color(image, box):
    """Cor dominante nao-branca dentro do box (ex.: icone de canto da
    boundary) -- no nosso estilo sintetico E nas convencoes reais da AWS, a
    cor do icone de canto bate com a cor da borda do retangulo (ver
    ICON_GROUPS em generate_synthetic_drawio.py), entao serve como "cor alvo"
    pra isolar a linha certa em meio a bordas aninhadas de outras cores.
    Prefere cor SATURADA (verde/vermelho/azul) quando existe -- mais seletiva
    pra separar boundaries aninhadas de cores diferentes -- mas icones reais
    de "Region"/"AZ" costumam ser so tracado preto/cinza (sem saturacao
    nenhuma); nesse caso cai pra cor mais escura consistente, senao a funcao
    retornava None sempre pra esses e o rastreamento caia no fallback de
    Canny generico (promiscuo demais em diagramas reais com bastante
    conteudo -- misturava varias boundaries/textos numa componente so)."""
    h, w = image.shape[:2]
    x0, y0, x1, y1 = [int(v) for v in box]
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w, x1), min(h, y1)
    crop = image[y0:y1, x0:x1]
    if crop.size == 0:
        return None
    pixels = crop.reshape(-1, 3).astype(np.int32)
    not_white = pixels.max(axis=1) < 240
    if not_white.sum() < 5:
        return None
    candidates = pixels[not_white]
    saturated = (candidates.max(axis=1) - candidates.min(axis=1)) > 20
    chosen = candidates[saturated] if saturated.sum() >= 5 else candidates
    return tuple(int(v) for v in np.median(chosen, axis=0))


def _trace_boundary_box(image, corner_box, exclude_boxes, search_radius=20):
    """Caixa detectada -> retangulo real, seguindo a linha da borda.

    Tenta por COR primeiro (mais seletivo quando ha varias boundaries
    aninhadas com bordas de cores diferentes bem proximas); cai pra Canny
    generico se o icone nao tiver uma cor dominante clara (ex.: preto/cinza).

    Busca na regiao da PROPRIA caixa detectada, expandida por
    search_radius em cada lado -- nao mais so um raio fixo em volta do
    centro. Antes do modelo ser retreinado com exemplos reais do retangulo
    INTEIRO (nao so o icone de canto ~24x24px, ver README/class_to_
    archetype.py), buscar perto do centro fazia sentido: a caixa bruta ERA
    so o icone, entao o centro dela ficava perto da linha. Depois do
    retreino a caixa bruta ja e uma estimativa razoavel do retangulo inteiro
    -- pra caixas grandes, o CENTRO fica longe de qualquer borda, e a busca
    num raio fixo de 20px nunca encontrava nada (ver investigacao: maioria
    das boundaries grandes ficava com rastreamento=None mesmo com a caixa
    bruta do YOLO ja razoavel).

    Entre os componentes conexos candidatos na janela, escolhe o de MAIOR
    IoU com a caixa bruta (nao o mais "populoso"): evita pegar a linha de
    uma boundary VIZINHA por acidente quando duas fronteiras proximas
    compartilham a mesma janela de busca (comum em diagramas densos, ex.
    Availability Zones lado a lado)."""
    h, w = image.shape[:2]
    color = _dominant_color(image, corner_box)
    if color is not None:
        diff = np.abs(image.astype(np.int32) - np.array(color)).sum(axis=2)
        mask = (diff < 60).astype(np.uint8) * 255
    else:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        mask = cv2.Canny(gray, 50, 150)

    for box in exclude_boxes:
        x0, y0, x1, y1 = [int(v) for v in box]
        mask[max(0, y0):y1, max(0, x0):x1] = 0
    # kernel maior que o das setas: precisa ligar os tracinhos de linhas
    # tracejadas (dashed), que tem gaps maiores que o padrao pontilhado fino
    # do glifo da seta.
    mask = cv2.dilate(mask, np.ones((5, 5), np.uint8), iterations=2)
    _, labels = cv2.connectedComponents(mask, connectivity=8)

    bx0, by0, bx1, by1 = corner_box
    y0r, y1r = max(0, int(by0) - search_radius), min(h, int(by1) + search_radius)
    x0r, x1r = max(0, int(bx0) - search_radius), min(w, int(bx1) + search_radius)
    region = labels[y0r:y1r, x0r:x1r]
    ids = np.unique(region[region > 0])
    if len(ids) == 0:
        return None

    best_box, best_iou = None, 0.15  # abaixo disso, candidato nao e confiavel
    for label_id in ids:
        ys, xs = np.where(labels == label_id)
        if len(xs) < 20:
            continue  # fragmento pequeno demais (ruido/texto), nao uma linha de verdade
        candidate = (float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max()))
        if _area(candidate) > 0.9 * w * h:
            continue  # vazou pra quase a imagem inteira, nao confiavel
        v = _iou(candidate, corner_box)
        if v > best_iou:
            best_iou, best_box = v, candidate
    return best_box


def build_trust_boundaries(boundary_dets, image, exclude_boxes):
    boundary_dets = _dedup_boundary_dets(boundary_dets)
    boundaries = []
    for i, d in enumerate(boundary_dets):
        traced = _trace_boundary_box(image, d.box, exclude_boxes)
        # Prioriza a caixa BRUTA do YOLO, so aceita o resultado do
        # rastreamento como REFINO quando ele concorda bastante com ela
        # (IoU>=0.5) -- nao mais o contrario. Antes do retreino com exemplos
        # reais do retangulo INTEIRO, a caixa bruta era so um icone de canto
        # ~24x24px e o rastreamento era essencial; hoje a caixa bruta ja e
        # uma estimativa razoavel por si so, e um rastreamento que diverge
        # muito dela tende a ter pego a linha de uma boundary VIZINHA por
        # engano (medido: usar so a caixa bruta bate F1=0.62 contra
        # ground truth, rastreamento sozinho (mesmo com a busca corrigida
        # pra usar a regiao da caixa em vez de um raio fixo no centro) fica
        # em 0.58 -- so aceitar quando concorda preserva o F1 do bruto e
        # ainda afina a borda exata quando o rastreamento é confiável).
        use_traced = traced is not None and _iou(traced, d.box) >= 0.5
        box = traced if use_traced else d.box
        name, ocr_btype, ocr_found = _ocr_boundary_label(image, box)

        # type: prioriza o SUB-TIPO do proprio YOLO (vpc/region/
        # availability_zone/... -- ver class_to_archetype.py::
        # BOUNDARY_SUBTYPES) quando a deteccao ja e especifica, mais
        # confiavel que o keyword-match do OCR (que so funciona se o texto
        # foi lido direito). Cai pro tipo inferido via OCR quando a
        # deteccao e o "boundary" generico (sem sub-tipo).
        btype = d.cls_name if d.cls_name != BOUNDARY_CLASS else ocr_btype

        notes = []
        if not use_traced:
            notes.append("rastreamento do retângulo falhou; usando apenas a caixa detectada")
        if not ocr_found:
            notes.append("rótulo não lido via OCR — name é placeholder")

        boundaries.append({
            "id": f"tb{i + 1}", "box": box, "name": name, "type": btype, "parent": None,
            "confidence": d.conf, "note": "; ".join(notes) or None,
        })

    for b in boundaries:
        candidates = [o for o in boundaries if o is not b and _contains(o["box"], b["box"])]
        if candidates:
            b["parent"] = min(candidates, key=lambda o: _area(o["box"]))["id"]

    # boundary implicita: cobre componentes fora de qualquer caixa detectada,
    # garantindo que Component.trust_boundary sempre resolve para algo valido.
    boundaries.append({"id": "external", "box": None, "name": "Externo / Não Detectado",
                        "type": "external", "parent": None, "confidence": None, "note": None})
    return boundaries


def _innermost_boundary(component_box, boundaries):
    containing = [b for b in boundaries if b["box"] is not None and _contains(b["box"], component_box)]
    if not containing:
        return "external"
    return min(containing, key=lambda b: _area(b["box"]))["id"]


def build_components(component_dets, boundaries, image):
    components = []
    counters = Counter()
    for d in component_dets:
        counters[d.cls_name] += 1
        idx = counters[d.cls_name]
        # d.cls_name pode ser um ARQUETIPO direto (fallback, ex. "compute")
        # ou um SERVICO especifico promovido (ex. "RDS", ver class_to_
        # archetype.py::FINE_GRAINED_SERVICES) -- category sempre rola pro
        # arquetipo; aws_service vem da propria deteccao quando especifica
        # (mais confiavel que OCR), senao cai no OCR+match de antes.
        category = _category_of(d.cls_name)
        detected_service = d.cls_name if d.cls_name != category else None

        # label_text ja vem limpo de ruido (_clean_ocr_text, ver
        # _ocr_component_label) -- sem newline embutido, sem token que e so
        # pontuacao/letra solta.
        label_text = _ocr_component_label(image, d.box)
        aws_service = detected_service or _match_aws_service(label_text)
        raw_fallback = False
        if aws_service is None and label_text and len(label_text) >= 3:
            # nao veio da deteccao nem bateu com AWS_SERVICE_NAMES via OCR,
            # mas o OCR LEU algo plausivel -- usa o proprio texto como
            # aws_service (best-effort) em vez de deixar null. Melhor um
            # palpite revisavel via HITL do que nada; a nota abaixo deixa
            # claro que nao foi validado contra a lista curada.
            aws_service = label_text
            raw_fallback = True

        notes = []
        if not label_text:
            notes.append("rótulo não lido via OCR")
        elif raw_fallback:
            notes.append(f"aws_service='{aws_service}' é o texto bruto do OCR (não bateu com nenhum serviço conhecido) — confira")

        components.append({
            "id": f"c_{d.cls_name}_{idx}",
            "box": d.box,
            # usa o rotulo lido via OCR quando disponivel (ex.: "Amazon RDS
            # (Master)"), senao cai no placeholder "{Arquétipo em PT-BR} {n}"
            # -- so o rotulo de EXIBICAO e traduzido (ARCHETYPE_LABEL_PT); o
            # `category` continua no identificador em ingles (ver comentario
            # em class_to_archetype.py::ARCHETYPE_LABEL_PT).
            "name": label_text if label_text else f"{ARCHETYPE_LABEL_PT.get(category, category)} {idx}",
            "aws_service": aws_service,
            "category": category,
            "element_type": ELEMENT_TYPE_OF.get(category, DEFAULT_ELEMENT_TYPE),
            "trust_boundary": _innermost_boundary(d.box, boundaries),
            "confidence": d.conf,
            "note": "; ".join(notes) or None,
        })
    return components


# --------------------------------------------------------------------------
# data flows: arrowhead -> destino (ponta) + rastreamento classico da linha
# ate o outro extremo -> origem. Heuristica geometrica, nao uma relacao
# aprendida -- fica ruidosa em diagramas densos com muitas linhas cruzadas.
# --------------------------------------------------------------------------

def _trace_far_endpoint(labels, arrowhead_box, tip, search_radius=40):
    x0, y0, x1, y1 = [int(v) for v in arrowhead_box]
    h, w = labels.shape
    y0r, y1r = max(0, y0 - search_radius), min(h, y1 + search_radius)
    x0r, x1r = max(0, x0 - search_radius), min(w, x1 + search_radius)
    region = labels[y0r:y1r, x0r:x1r]
    ids, counts = np.unique(region[region > 0], return_counts=True)
    if len(ids) == 0:
        return None
    label_id = ids[np.argmax(counts)]
    ys, xs = np.where(labels == label_id)
    if len(xs) == 0:
        return None
    dists = (xs - tip[0]) ** 2 + (ys - tip[1]) ** 2
    far_idx = int(np.argmax(dists))
    return float(xs[far_idx]), float(ys[far_idx])


def build_data_flows(arrowhead_dets, components, boundary_boxes, image):
    if not arrowhead_dets or not components:
        return []

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    mask = cv2.Canny(gray, 50, 150)
    # apaga pixels dentro de componentes/fronteiras: sobra so o traco das linhas
    for box in [c["box"] for c in components] + boundary_boxes:
        x0, y0, x1, y1 = [int(v) for v in box]
        mask[max(0, y0):y1, max(0, x0):x1] = 0
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1)
    _, labels = cv2.connectedComponents(mask, connectivity=8)

    flows = []
    for i, d in enumerate(arrowhead_dets):
        tip = _center(d.box)
        dest = _nearest_component(tip, components)
        if dest is None:
            continue

        far_point = _trace_far_endpoint(labels, d.box, tip)
        source = _nearest_component(far_point, components) if far_point else None
        if source is None or source["id"] == dest["id"]:
            continue

        protocol = _ocr_flow_protocol(image, tip, far_point)
        flows.append({
            "id": f"f{i + 1}",
            "source": source["id"],
            "destination": dest["id"],
            "protocol": protocol or "desconhecido",
            "crosses_boundary": source["trust_boundary"] != dest["trust_boundary"],
            "confidence": d.conf,
            "note": None if protocol else "protocolo não lido via OCR",
        })
    return flows


# --------------------------------------------------------------------------
# montagem do ArchitectureDiagram
# --------------------------------------------------------------------------

def build_architecture_diagram(dets: list[Det], image) -> ArchitectureDiagram:
    boundary_dets = [d for d in dets if d.cls_name in BOUNDARY_CLASSES]
    arrowhead_dets = [d for d in dets if d.cls_name == ARROWHEAD_CLASS]
    component_dets = [d for d in dets if d.cls_name not in BOUNDARY_CLASSES and d.cls_name != ARROWHEAD_CLASS]

    # exclui componentes/setas do rastreamento da borda (pra nao "vazar" pra
    # dentro dos icones), mas NAO exclui outras boundaries -- a linha de uma
    # boundary pode legitimamente passar por baixo/perto de outra aninhada.
    exclude_for_tracing = [d.box for d in component_dets] + [d.box for d in arrowhead_dets]
    boundaries = build_trust_boundaries(boundary_dets, image, exclude_for_tracing)
    components = build_components(component_dets, boundaries, image)
    flows = build_data_flows(
        arrowhead_dets, components, [b["box"] for b in boundaries if b["box"] is not None], image
    )

    confidences = [d.conf for d in dets] or [0.0]
    avg_conf = sum(confidences) / len(confidences)
    confidence = "alta" if avg_conf >= 0.7 else "média" if avg_conf >= 0.4 else "baixa"
    region = next((b["name"] for b in boundaries if b["type"] == "region"), None)

    return ArchitectureDiagram.model_validate({
        "diagram_metadata": {"cloud_provider": "aws", "region": region, "extraction_confidence": confidence},
        "trust_boundaries": [
            {
                "id": b["id"], "name": b["name"], "type": b["type"], "parent": b["parent"],
                "confidence": b["confidence"], "note": b["note"],
            }
            for b in boundaries
        ],
        "components": [
            {
                "id": c["id"], "name": c["name"], "aws_service": c["aws_service"],
                "element_type": c["element_type"], "category": c["category"],
                "trust_boundary": c["trust_boundary"], "instance_count": None,
                "confidence": c["confidence"], "note": c["note"],
            }
            for c in components
        ],
        "data_flows": flows,
    })


def detect_architecture(image_path: str) -> ArchitectureDiagram:
    from ultralytics import YOLO  # import tardio: so quem roda inferencia precisa de torch/ultralytics

    model = YOLO(WEIGHTS)
    result = model.predict(source=image_path, conf=CONF, imgsz=IMGSZ, verbose=False)[0]
    names = result.names
    dets = [
        Det(names[int(cls_id)], tuple(box), float(conf))
        for box, cls_id, conf in zip(
            result.boxes.xyxy.tolist(), result.boxes.cls.tolist(), result.boxes.conf.tolist()
        )
    ]
    result.save(filename="deteccao_saida.jpg")
    return build_architecture_diagram(dets, result.orig_img)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python predict.py <imagem>")
        sys.exit(1)

    diagram = detect_architecture(sys.argv[1])

    print("Componentes detectados (arquetipo: quantidade):")
    for arch, n in Counter(c.category for c in diagram.components).most_common():
        print(f"  {arch}: {n}")

    print(f"\nTrust boundaries detectadas: {len(diagram.trust_boundaries)}")
    for tb in diagram.trust_boundaries:
        parent = f" (dentro de {tb.parent})" if tb.parent else ""
        print(f"  {tb.id}: {tb.name} [{tb.type}]{parent}")

    print(f"\nData flows detectados: {len(diagram.data_flows)}")
    for f in diagram.data_flows:
        cross = " [cruza trust boundary]" if f.crosses_boundary else ""
        print(f"  {f.source} -> {f.destination} ({f.protocol}){cross}")

    out_path = Path(sys.argv[1]).stem + "_architecture.json"
    Path(out_path).write_text(diagram.model_dump_json(indent=2), encoding="utf-8")
    print(f"\nArchitectureDiagram salvo em {out_path}")
