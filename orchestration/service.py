"""Ponto de entrada de serviço da orquestração STRIDE (consumido pelo Dev 4).

Empacota o ciclo do grafo (invoke → interrupt → resume) em três funções que
sempre retornam `GraphStateResponse` (o contrato de polling):

- `run_analysis(diagram)`        — inicia a análise; roda até pausar no HITL.
- `send_hitl_message(thread, ...)` — retoma com a decisão do usuário (approve/refine).
- `get_analysis_state(thread)`   — lê o estado atual sem avançar (polling).

Notas:
- O grafo roda de forma síncrona até o checkpoint HITL. Para "responder
  imediatamente + polling" (ver risco de timeout no CLAUDE.md), o Dev 4 deve
  chamar `run_analysis` em background (ex.: FastAPI BackgroundTasks) e usar
  `get_analysis_state` para o polling.
- O LangGraph NÃO materializa canais com valor None — por isso todo acesso ao
  estado usa `.get()` com defaults.
- Erros não tratados pelos nós (ex.: chave de API ausente — risco R1) são
  capturados aqui e viram `status="error"`, em vez de derrubar o processo.
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from langgraph.types import Command

from extraction.schemas import ArchitectureDiagram
from orchestration.graph import get_compiled_graph
from orchestration.models import GraphStateResponse

logger = logging.getLogger(__name__)


def _config(diagram: Optional[ArchitectureDiagram], thread_id: str) -> dict:
    # ~2N+3 super-steps na análise inicial; folga para ciclos de refinamento.
    n = len(diagram.components) if diagram else 0
    recursion_limit = max(50, 2 * n + 20)
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": recursion_limit}


def _extract_hitl_summary(snapshot) -> Optional[list[dict]]:
    for task in snapshot.tasks:
        for interrupt in getattr(task, "interrupts", ()) or ():
            payload = interrupt.value
            if isinstance(payload, dict) and "summary" in payload:
                return payload["summary"]
    return None


def _build_response(thread_id: str, snapshot) -> GraphStateResponse:
    values = snapshot.values or {}
    diagram = values.get("diagram")
    analyses = values.get("component_analyses", {})
    failed = values.get("failed_component_ids", [])
    report = values.get("report")

    if diagram is None:
        # Sem estado para este thread (desconhecido / não iniciado).
        return GraphStateResponse(
            thread_id=thread_id,
            status="error",
            components_analyzed_count=0,
            components_total=0,
        )

    if values.get("error"):
        status = "error"
    elif snapshot.next == ("hitl_review",):
        status = "hitl_pending"
    elif not snapshot.next and report is not None:
        status = "completed"
    else:
        status = "running"

    hitl_summary = _extract_hitl_summary(snapshot) if status == "hitl_pending" else None

    return GraphStateResponse(
        thread_id=thread_id,
        status=status,
        components_analyzed_count=len(analyses),
        components_total=len(diagram.components),
        analyzed_component_ids=list(analyses.keys()),
        components_failed_count=len(failed),
        hitl_summary=hitl_summary,
        report=report,
    )


def _error_response(thread_id: str) -> GraphStateResponse:
    try:
        base = get_analysis_state(thread_id)
        return base.model_copy(update={"status": "error"})
    except Exception:  # noqa: BLE001 — último recurso: resposta de erro mínima
        return GraphStateResponse(
            thread_id=thread_id,
            status="error",
            components_analyzed_count=0,
            components_total=0,
        )


def run_analysis(
    diagram: ArchitectureDiagram, thread_id: Optional[str] = None
) -> GraphStateResponse:
    """Inicia a análise. Roda até pausar no HITL (ou concluir/erro)."""
    thread_id = thread_id or f"analysis-{uuid.uuid4().hex[:12]}"
    compiled = get_compiled_graph()
    config = _config(diagram, thread_id)

    logger.info(
        "run_analysis — thread=%s components=%d", thread_id, len(diagram.components)
    )
    try:
        compiled.invoke({"diagram": diagram}, config)
    except Exception as exc:  # noqa: BLE001 — nunca derruba o processo (ver R1)
        logger.warning("run_analysis erro — thread=%s tipo=%s", thread_id, type(exc).__name__)
        return _error_response(thread_id)

    return get_analysis_state(thread_id)


def send_hitl_message(
    thread_id: str, action: str, feedback: Optional[str] = None
) -> GraphStateResponse:
    """Retoma a análise pausada com a decisão do usuário.

    action="approve" -> gera o relatório; action="refine" (+feedback) -> refina.
    """
    compiled = get_compiled_graph()
    base_config = {"configurable": {"thread_id": thread_id}}
    snapshot = compiled.get_state(base_config)
    diagram = (snapshot.values or {}).get("diagram")

    resume: dict = {"action": action}
    if feedback is not None:
        resume["feedback"] = feedback

    logger.info("send_hitl_message — thread=%s action=%s", thread_id, action)
    try:
        compiled.invoke(Command(resume=resume), _config(diagram, thread_id))
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "send_hitl_message erro — thread=%s tipo=%s", thread_id, type(exc).__name__
        )
        return _error_response(thread_id)

    return get_analysis_state(thread_id)


def get_analysis_state(thread_id: str) -> GraphStateResponse:
    """Lê o estado atual do thread sem avançar o grafo (polling)."""
    compiled = get_compiled_graph()
    snapshot = compiled.get_state({"configurable": {"thread_id": thread_id}})
    return _build_response(thread_id, snapshot)
