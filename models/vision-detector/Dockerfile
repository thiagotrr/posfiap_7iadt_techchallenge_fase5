FROM python:3.11-slim

# libgl1/libglib2.0-0 are required by opencv (a transitive dependency of ultralytics).
# tesseract-ocr is the binary pytesseract shells out to (best-effort OCR of
# trust-boundary labels and data-flow protocol text in predict.py).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Pinned to the CUDA 12.8 wheel index because Blackwell GPUs (e.g. RTX 5070,
# sm_120) aren't supported by the torch build that `pip install ultralytics`
# would otherwise pull in (that one tops out around sm_90 and fails at
# runtime with "no kernel image is available for execution on the device").
# Installed both before AND after ultralytics: ultralytics declares its own
# torch version range, and pip is free to swap in a different (CPU/older-CUDA)
# build to satisfy it, silently undoing the pin. Re-asserting it afterwards
# guarantees the final image still has the cu128 build regardless of what
# ultralytics' own resolution did in between.
RUN pip install --no-cache-dir torch==2.9.1+cu128 torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/cu128

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir torch==2.9.1+cu128 torchvision torchaudio \
       --index-url https://download.pytorch.org/whl/cu128

COPY . .

# Default: sobe o servidor HTTP (api.py), consumido por extraction/service.py
# via VISION_DETECTOR_URL (ver docker-compose.yml, serviço vision-detector).
# Scripts de treino/avaliação continuam acessíveis via `docker compose run
# --rm vision-detector python train.py` etc., que sobrescreve esse comando.
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
