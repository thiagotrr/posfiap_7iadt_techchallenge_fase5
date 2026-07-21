"""
extraction/router.py

FastAPI APIRouter da extração de diagramas de arquitetura (vision-detector).
Prefixo esperado: /api/v1/extraction/ (aplicado na hora do registro em
app/routers/__init__.py -- as rotas aqui são relativas, mesmo padrão de
knowledge/router.py).
"""

from __future__ import annotations

import logging
import os

import httpx
from fastapi import APIRouter, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from extraction.exceptions import (
    ExtractionFailedError,
    PatchElementNotFoundError,
    PatchValidationError,
)
from extraction.schemas import ArchitectureDiagram, DiagramPatch
from extraction.service import apply_patch, extract_diagram

logger = logging.getLogger(__name__)
router = APIRouter(tags=["extraction"])


@router.get("/health")
def extraction_health() -> JSONResponse:
    """
    Health-check da extração.

    Se VISION_DETECTOR_URL estiver configurada, verifica se o serviço
    vision-detector está acessível. Se não estiver, a extração roda em modo
    de import direto (ver extraction/service.py) e não há serviço externo
    para checar.
    """
    vision_detector_url = os.environ.get("VISION_DETECTOR_URL")

    if not vision_detector_url:
        return JSONResponse(
            status_code=200,
            content={"status": "ok", "mode": "import", "vision_detector_url": None},
        )

    try:
        response = httpx.get(f"{vision_detector_url.rstrip('/')}/health", timeout=5.0)
        response.raise_for_status()
        return JSONResponse(
            status_code=200,
            content={"status": "ok", "mode": "http", "vision_detector_url": vision_detector_url},
        )
    except httpx.HTTPError as exc:
        logger.error("Extraction health check failed - %s", exc)
        return JSONResponse(
            status_code=503,
            content={
                "status": "unavailable",
                "mode": "http",
                "vision_detector_url": vision_detector_url,
                "error": "Serviço vision-detector não está acessível.",
                "detail": str(exc),
            },
        )


@router.post("/diagram")
async def create_diagram(image: UploadFile) -> JSONResponse:
    """
    Extrai um ArchitectureDiagram a partir de uma imagem de diagrama de
    arquitetura enviada (multipart/form-data, campo `image`).

    Returns:
        200 — ArchitectureDiagram extraído.
        502 — vision-detector inacessível ou a extração falhou.
    """
    image_bytes = await image.read()
    mime_type = image.content_type or "image/png"

    try:
        diagram = extract_diagram(image_bytes, mime_type=mime_type)
    except ExtractionFailedError as exc:
        logger.error("Diagram extraction failed - %s", exc)
        return JSONResponse(
            status_code=502,
            content={"error": "ExtractionFailedError", "detail": str(exc)},
        )

    return JSONResponse(status_code=200, content=diagram.model_dump())


class DiagramPatchRequest(BaseModel):
    diagram: ArchitectureDiagram
    patch: DiagramPatch


@router.post("/diagram/patch")
def patch_diagram(body: DiagramPatchRequest) -> JSONResponse:
    """
    Aplica correções HITL (update/add/remove) a um ArchitectureDiagram já
    extraído e retorna o diagrama corrigido.

    Returns:
        200 — ArchitectureDiagram corrigido.
        404 — algum element_id referenciado no patch não existe.
        422 — o resultado final do patch seria um diagrama inválido.
    """
    try:
        corrected = apply_patch(body.diagram, body.patch)
    except PatchElementNotFoundError as exc:
        return JSONResponse(
            status_code=404,
            content={"error": "PatchElementNotFoundError", "detail": str(exc)},
        )
    except PatchValidationError as exc:
        return JSONResponse(
            status_code=422,
            content={"error": "PatchValidationError", "detail": str(exc)},
        )

    return JSONResponse(status_code=200, content=corrected.model_dump())
