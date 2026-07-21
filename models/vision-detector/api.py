"""
models/vision-detector/api.py

Servidor FastAPI do container `vision-detector`: expõe a detecção via HTTP
para que `extraction/service.py` (raiz do repo) chame por rede, sem precisar
de torch/ultralytics/opencv instalados na imagem da API principal -- ver
`extraction/service.py::_extract_via_http`.

É o comando default do container (ver Dockerfile / docker-compose.yml,
serviço `vision-detector`). Os scripts de treino/avaliação continuam
acessíveis via `docker compose run --rm vision-detector python train.py`
etc., que sobrescreve esse comando default.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, UploadFile
from fastapi.responses import JSONResponse

logging.basicConfig(level="INFO", format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
logger = logging.getLogger(__name__)

# Mesmo repo/arquivo documentados em README.md ("Modelo e dataset no Hugging Face").
_HF_REPO_ID = "luisasousa/aws-architecture-vision-detector"
_HF_FILENAME = "best.pt"
# Mesmo caminho relativo que predict.py usa via WEIGHTS ("runs/detect/stride/weights/best.pt").
_WEIGHTS_PATH = Path(__file__).resolve().parent / "runs" / "detect" / "stride" / "weights" / "best.pt"

_MANUAL_DOWNLOAD_HINT = (
    f"hf download {_HF_REPO_ID} {_HF_FILENAME} --local-dir {_WEIGHTS_PATH.parent}"
)

# Duas formas de ter pesos: usar os pré-treinados do Hugging Face (padrão,
# baixados aqui) ou treinar localmente (`docker compose run --rm
# vision-detector python train.py`, precisa do dataset -- ver README).
# Quem treinou localmente já tem best.pt em disco, então _ensure_weights()
# nunca sobrescreve: só baixa quando o arquivo está ausente. Essa env var
# existe pra quem quer desligar até a TENTATIVA de download (ex.: ambiente
# sempre offline, ou já sabe que vai treinar e não quer o log de erro de
# rede no startup).
_AUTO_DOWNLOAD_WEIGHTS = os.environ.get("VISION_DETECTOR_AUTO_DOWNLOAD_WEIGHTS", "true").lower() not in (
    "false", "0", "no",
)


def _ensure_weights() -> None:
    """Baixa os pesos treinados do Hugging Face se ainda não estiverem em
    disco (primeiro `docker compose up`, volume novo, etc.) e o download
    automático não estiver desligado (VISION_DETECTOR_AUTO_DOWNLOAD_WEIGHTS).
    Best-effort: se falhar (ex.: sem internet), só loga a instrução de
    download manual ou de treino local -- os endpoints seguem de pé e
    reportam pesos ausentes em vez de derrubar o container."""
    if _WEIGHTS_PATH.exists():
        logger.info("Pesos já presentes em %s", _WEIGHTS_PATH)
        return

    if not _AUTO_DOWNLOAD_WEIGHTS:
        logger.info(
            "Download automático desligado (VISION_DETECTOR_AUTO_DOWNLOAD_WEIGHTS=false) e pesos ausentes em %s "
            "-- baixe manualmente (%s) ou treine localmente: docker compose run --rm vision-detector python train.py "
            "(precisa do dataset, ver README).",
            _WEIGHTS_PATH, _MANUAL_DOWNLOAD_HINT,
        )
        return

    logger.info("Pesos não encontrados em %s -- baixando do Hugging Face (%s)...", _WEIGHTS_PATH, _HF_REPO_ID)
    try:
        from huggingface_hub import hf_hub_download

        _WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        downloaded = hf_hub_download(repo_id=_HF_REPO_ID, filename=_HF_FILENAME)
        shutil.copy(downloaded, _WEIGHTS_PATH)
        logger.info("Pesos baixados com sucesso em %s", _WEIGHTS_PATH)
    except Exception:
        logger.exception(
            "Download automático dos pesos falhou (rede indisponível?). Baixe manualmente (%s) ou treine "
            "localmente: docker compose run --rm vision-detector python train.py (precisa do dataset, ver README).",
            _MANUAL_DOWNLOAD_HINT,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_weights()
    yield


app = FastAPI(title="vision-detector", version="1.0.0", lifespan=lifespan)


@app.get("/health")
def health() -> JSONResponse:
    weights_ok = _WEIGHTS_PATH.exists()
    return JSONResponse(
        status_code=200 if weights_ok else 503,
        content={
            "status": "ok" if weights_ok else "unavailable",
            "weights_present": weights_ok,
            "weights_path": str(_WEIGHTS_PATH),
            "auto_download_enabled": _AUTO_DOWNLOAD_WEIGHTS,
            "manual_download": None if weights_ok else _MANUAL_DOWNLOAD_HINT,
            "train_locally": None if weights_ok else (
                "docker compose run --rm vision-detector python train.py (precisa do dataset, ver README)"
            ),
        },
    )


@app.post("/predict")
async def predict(image: UploadFile) -> JSONResponse:
    if not _WEIGHTS_PATH.exists():
        return JSONResponse(
            status_code=503,
            content={
                "error": "WeightsNotFoundError",
                "detail": f"Pesos treinados não encontrados. Baixe manualmente: {_MANUAL_DOWNLOAD_HINT}",
            },
        )

    from predict import detect_architecture  # import tardio: só quem chama /predict paga o custo de carregar torch

    image_bytes = await image.read()
    suffix = Path(image.filename or "diagram.png").suffix or ".png"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
        tmp.write(image_bytes)
        tmp.flush()
        try:
            diagram = detect_architecture(tmp.name)
        except Exception as exc:
            logger.exception("Detecção falhou")
            return JSONResponse(status_code=500, content={"error": "DetectionFailedError", "detail": str(exc)})

    return JSONResponse(status_code=200, content=diagram.model_dump())
