"""Router FastAPI da orquestração STRIDE (montável pelo Dev 4).

Camada HTTP fina sobre `orchestration.service`. O Dev 4 monta com:

    from orchestration.router import router
    app.include_router(router, prefix="/api")   # prefixo à escolha do Dev 4

Rotas:
    GET  /health                          — healthcheck
    POST /analyses                        — inicia análise (body: ArchitectureDiagram)
    GET  /analyses/{thread_id}            — estado atual (polling)
    POST /analyses/{thread_id}/messages   — decisão HITL (approve/refine)
    GET  /analyses/{thread_id}/report     — STRIDEReport final (404 se indisponível)

Nota de execução: `POST /analyses` roda de forma síncrona até o checkpoint HITL.
O FastAPI executa endpoints síncronos num threadpool (não bloqueia o event loop).
Para "responder na hora + polling" (risco de timeout, ver CLAUDE.md), o Dev 4
pode envolver `service.run_analysis` em BackgroundTasks e usar o GET de estado.
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from extraction.schemas import ArchitectureDiagram
from orchestration import service
from orchestration.models import GraphStateResponse, STRIDEReport

router = APIRouter(tags=["orchestration"])


class HITLMessageRequest(BaseModel):
    action: Literal["approve", "refine"]
    feedback: Optional[str] = None


def _is_unknown(response: GraphStateResponse) -> bool:
    # get_analysis_state devolve error + total 0 para thread inexistente.
    return response.status == "error" and response.components_total == 0


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.post("/analyses", response_model=GraphStateResponse)
def start_analysis(diagram: ArchitectureDiagram) -> GraphStateResponse:
    return service.run_analysis(diagram)


@router.get("/analyses/{thread_id}", response_model=GraphStateResponse)
def get_state(thread_id: str) -> GraphStateResponse:
    response = service.get_analysis_state(thread_id)
    if _is_unknown(response):
        raise HTTPException(status_code=404, detail="Análise não encontrada.")
    return response


@router.post("/analyses/{thread_id}/messages", response_model=GraphStateResponse)
def post_hitl_message(thread_id: str, body: HITLMessageRequest) -> GraphStateResponse:
    # refine exige feedback; approve o ignora.
    if body.action == "refine" and not body.feedback:
        raise HTTPException(
            status_code=422, detail="feedback é obrigatório para action=refine."
        )
    response = service.send_hitl_message(thread_id, body.action, body.feedback)
    if _is_unknown(response):
        raise HTTPException(status_code=404, detail="Análise não encontrada.")
    return response


@router.get("/analyses/{thread_id}/report", response_model=STRIDEReport)
def get_report(thread_id: str) -> STRIDEReport:
    response = service.get_analysis_state(thread_id)
    if _is_unknown(response):
        raise HTTPException(status_code=404, detail="Análise não encontrada.")
    if response.report is None:
        raise HTTPException(
            status_code=404, detail="Relatório ainda não disponível para esta análise."
        )
    return response.report
