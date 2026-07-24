from fastapi import APIRouter, FastAPI

from extraction.router import router as extraction_router
from knowledge.router import router as knowledge_router
from orchestration.router import router as orchestration_router

health_router = APIRouter(tags=["health"])


@health_router.get("/health")
def health_check() -> dict:
    return {"status": "ok", "version": "1.0.0"}


def register_routers(app: FastAPI) -> None:
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(extraction_router, prefix="/api/v1/extraction")
    app.include_router(knowledge_router, prefix="/api/v1/knowledge")
    app.include_router(orchestration_router, prefix="/api/v1/orchestration")
