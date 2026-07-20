"""Orquestração de alto nível do módulo extraction: extrai um
ArchitectureDiagram a partir de uma imagem e aplica patches de correção HITL.

extract_diagram() tem dois modos, escolhidos pela variável de ambiente
VISION_DETECTOR_URL:

  - Definida (default em docker-compose.yml: http://vision-detector:8000) --
    chama o serviço HTTP do container `vision-detector` via httpx. É o modo
    usado em Docker: a imagem da API principal não precisa de
    torch/ultralytics/opencv instalados, só de httpx (já é dependência do
    projeto).
  - Ausente -- import direto de models/vision-detector/predict.py (import
    tardio, mesma lógica de antes), para quem quer usar o modelo sem subir
    o container vision-detector (notebook, script local, outro serviço que
    já tenha as dependências pesadas do vision-detector instaladas -- ver
    models/vision-detector/requirements.txt).

Nenhum dos dois modos importa cv2/numpy/ultralytics/httpx no carregamento do
módulo em si -- a escolha e a chamada pesada acontecem dentro de
extract_diagram(), só quando ele é de fato chamado.
"""

import logging
import os
import sys
import tempfile
from pathlib import Path

from pydantic import ValidationError

from extraction.exceptions import (
    ExtractionFailedError,
    PatchElementNotFoundError,
    PatchValidationError,
)
from extraction.schemas import ArchitectureDiagram, DiagramPatch, ElementPatch

logger = logging.getLogger(__name__)

_VISION_DETECTOR_DIR = Path(__file__).resolve().parent.parent / "models" / "vision-detector"

_MIME_TO_SUFFIX = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
}

_COLLECTION_FIELD = {
    "component": "components",
    "data_flow": "data_flows",
    "trust_boundary": "trust_boundaries",
}

# Generoso porque, em CPU, a primeira chamada inclui carregar os pesos do
# YOLO e, se ainda não estiverem em disco, o download automático do
# Hugging Face feito pelo próprio container vision-detector no startup
# (ver models/vision-detector/api.py) -- pode levar bem mais que o default
# de alguns segundos do httpx.
_HTTP_TIMEOUT_S = 120.0


def extract_diagram(image_bytes: bytes, mime_type: str = "image/png") -> ArchitectureDiagram:
    """Detecta um diagrama de arquitetura a partir dos bytes de uma imagem.

    Usa o serviço HTTP do vision-detector se VISION_DETECTOR_URL estiver
    definida no ambiente; caso contrário, importa o detector direto neste
    processo (ver docstring do módulo).
    """
    vision_detector_url = os.environ.get("VISION_DETECTOR_URL")
    logger.info(
        "Extraction started - provider=vision-detector mode=%s mime_type=%s",
        "http" if vision_detector_url else "import", mime_type,
    )

    if vision_detector_url:
        diagram = _extract_via_http(vision_detector_url, image_bytes, mime_type)
    else:
        diagram = _extract_via_import(image_bytes, mime_type)

    logger.info(
        "Extraction completed - components=%d flows=%d confidence=%s",
        len(diagram.components), len(diagram.data_flows), diagram.diagram_metadata.extraction_confidence,
    )
    return diagram


def _extract_via_http(base_url: str, image_bytes: bytes, mime_type: str) -> ArchitectureDiagram:
    import httpx  # import tardio: só quem usa o modo HTTP precisa disso carregado

    suffix = _MIME_TO_SUFFIX.get(mime_type, ".png")
    try:
        response = httpx.post(
            f"{base_url.rstrip('/')}/predict",
            files={"image": (f"diagram{suffix}", image_bytes, mime_type)},
            timeout=_HTTP_TIMEOUT_S,
        )
        response.raise_for_status()
        return ArchitectureDiagram.model_validate(response.json())
    except (httpx.HTTPError, ValidationError) as e:
        logger.error("Extraction failed (http, url=%s) - %s", base_url, e)
        raise ExtractionFailedError(
            f"Falha ao extrair diagrama via serviço vision-detector ({base_url})"
        ) from e


def _extract_via_import(image_bytes: bytes, mime_type: str) -> ArchitectureDiagram:
    suffix = _MIME_TO_SUFFIX.get(mime_type, ".png")

    if str(_VISION_DETECTOR_DIR) not in sys.path:
        sys.path.insert(0, str(_VISION_DETECTOR_DIR))

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
        tmp.write(image_bytes)
        tmp.flush()
        try:
            from predict import detect_architecture  # import tardio: evita torch/cv2 no import do pacote

            return detect_architecture(tmp.name)
        except Exception as e:
            logger.error("Extraction failed (import) - %s", e)
            raise ExtractionFailedError("Falha ao extrair diagrama da imagem enviada") from e


def _find_index(items: list[dict], element_id: str) -> int | None:
    return next((i for i, el in enumerate(items) if el.get("id") == element_id), None)


def _apply_one(data: dict, patch: ElementPatch) -> None:
    if patch.element_type == "metadata":
        data["diagram_metadata"][patch.field] = patch.value
        logger.info("HITL patch applied - element_type=metadata field=%s value=%r", patch.field, patch.value)
        return

    items = data[_COLLECTION_FIELD[patch.element_type]]

    if patch.op == "add":
        items.append(patch.value)
        logger.info("HITL patch applied - op=add element_type=%s id=%s", patch.element_type, patch.value.get("id"))
        return

    idx = _find_index(items, patch.element_id)
    if idx is None:
        logger.warning("HITL patch element not found - element_type=%s id=%s", patch.element_type, patch.element_id)
        raise PatchElementNotFoundError(patch.element_type, patch.element_id)

    if patch.op == "remove":
        items.pop(idx)
        logger.info("HITL patch applied - op=remove element_type=%s id=%s", patch.element_type, patch.element_id)
    else:
        items[idx][patch.field] = patch.value
        logger.info(
            "HITL patch applied - op=update element_type=%s id=%s field=%s value=%r",
            patch.element_type, patch.element_id, patch.field, patch.value,
        )


def apply_patch(diagram: ArchitectureDiagram, patch: DiagramPatch) -> ArchitectureDiagram:
    """Aplica um DiagramPatch (update/add/remove) e retorna um novo
    ArchitectureDiagram re-validado. Não muta `diagram`.

    Os patches de um mesmo DiagramPatch são aplicados como uma transação:
    a re-validação de integridade referencial roda uma vez, no final, sobre
    o resultado de todos eles -- permite, por exemplo, remover um componente
    e os data flows que o referenciam no mesmo patch sem falhar no meio.
    """
    data = diagram.model_dump()

    for p in patch.patches:
        _apply_one(data, p)

    try:
        return ArchitectureDiagram.model_validate(data)
    except ValidationError as e:
        raise PatchValidationError(str(e)) from e
