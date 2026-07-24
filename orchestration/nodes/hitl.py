"""Nó: hitl_review — ponto de checkpoint Human-in-the-Loop (interrupt real).

Pausa o grafo com `interrupt()` e devolve ao chamador um resumo das análises para
o usuário aprovar ou refinar. A retomada é feita com `Command(resume=<decisão>)`
(ver service.send_hitl_message no Épico 4).

Formato da decisão de retomada (dict):
    {"action": "approve"}                          -> segue para o relatório
    {"action": "refine", "feedback": "<texto>"}    -> segue para refine_analysis

Idempotência: ao retomar, o LangGraph RE-EXECUTA o nó do início (o `interrupt()`
passa a devolver o valor em vez de pausar). Todo o código antes do `interrupt()`
apenas lê o estado e monta o resumo — é idempotente por construção.
"""
from __future__ import annotations

import logging

from langgraph.types import interrupt

from orchestration.state import GraphState

logger = logging.getLogger(__name__)


def _build_hitl_summary(state: GraphState) -> list[dict]:
    """Resumo por componente para o usuário decidir (alimenta hitl_summary do
    GraphStateResponse)."""
    resumo: list[dict] = []
    for component_id, analysis in state["component_analyses"].items():
        resumo.append(
            {
                "component_id": component_id,
                "component_name": analysis.component_name,
                "threats_count": len(analysis.stride_entries),
            }
        )
    return resumo


def hitl_review(state: GraphState) -> dict:
    summary = _build_hitl_summary(state)

    logger.info(
        "HITL review — pausa para revisão (componentes=%d)", len(summary)
    )

    # Pausa o grafo. `decision` recebe o que for enviado via Command(resume=...).
    decision = interrupt(
        {
            "type": "hitl_review",
            "message": (
                "Revise a análise STRIDE. Responda com "
                '{"action": "approve"} para gerar o relatório ou '
                '{"action": "refine", "feedback": "..."} para refinar.'
            ),
            "summary": summary,
        }
    )

    decision = decision or {}
    action = decision.get("action", "approve")  # default defensivo: aprovar
    feedback = decision.get("feedback")

    if action == "refine":
        logger.info("HITL review — refinamento solicitado")
        return {"hitl_approved": False, "hitl_feedback": feedback}

    logger.info("HITL review — análise aprovada")
    return {"hitl_approved": True, "hitl_feedback": None}
