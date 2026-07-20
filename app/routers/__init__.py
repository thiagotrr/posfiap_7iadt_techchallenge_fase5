from fastapi import APIRouter, FastAPI

from knowledge.router import router as knowledge_router

health_router = APIRouter(tags=["health"])


@health_router.get("/health")
def health_check() -> dict:
    return {"status": "ok", "version": "1.0.0"}


def _stub_router(module_name: str) -> APIRouter:
    router = APIRouter(tags=[module_name])

    @router.api_route("/{path:path}", methods=["GET", "POST", "PATCH", "DELETE"])
    def not_yet_integrated(path: str) -> None:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail=f"{module_name} not yet integrated")

    return router


def register_routers(app: FastAPI) -> None:
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(_stub_router("extraction"), prefix="/api/v1/extraction")
    app.include_router(knowledge_router, prefix="/api/v1/knowledge")
    app.include_router(_stub_router("orchestration"), prefix="/api/v1/orchestration")
