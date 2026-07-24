"""Nó: refine_analysis — refina as análises com base no feedback do usuário (LLM).

Aplica o `hitl_feedback` a cada ComponentAnalysis via LLM (REFINEMENT_*), usando
o mesmo retry de validação da geração. Se o refinamento de um componente falha,
**mantém a análise atual** (nunca perde o resultado anterior). Depois volta ao
hitl_review para nova rodada de revisão.

Escopo: refina TODOS os componentes analisados com o mesmo feedback. Refinamento
direcionado a um componente específico é melhoria futura (o payload de decisão
poderia carregar um component_id).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from orchestration.llm_client import LLMAnalysisClient, analyze_with_validation_retry
from orchestration.models import ComponentAnalysis
from orchestration.prompts import (
    REFINEMENT_SYSTEM_PROMPT,
    REFINEMENT_USER_TEMPLATE,
    stride_entries_json_schema,
)
from orchestration.state import GraphState

logger = logging.getLogger(__name__)


def _refine_component(client, schema, analysis: ComponentAnalysis, feedback: str):
    current_analysis = json.dumps(
        [entry.model_dump() for entry in analysis.stride_entries], ensure_ascii=False
    )
    user_prompt = REFINEMENT_USER_TEMPLATE.format(
        current_analysis=current_analysis,
        user_feedback=feedback,
        json_schema=json.dumps(schema, ensure_ascii=False),
    )
    return analyze_with_validation_retry(
        client, REFINEMENT_SYSTEM_PROMPT, user_prompt, schema
    )


def refine_analysis(state: GraphState) -> dict:
    # .get(): LangGraph não materializa canais None.
    feedback = state.get("hitl_feedback")
    chat_history = list(state.get("chat_history", []))
    if feedback:
        chat_history.append({"role": "user", "content": feedback})

    analyses = state["component_analyses"]

    if not feedback:
        logger.info("refine_analysis: sem feedback — nenhuma alteração")
        return {"chat_history": chat_history, "hitl_feedback": None}

    client = LLMAnalysisClient()
    schema = stride_entries_json_schema()

    refined = dict(analyses)
    refined_count = 0
    for component_id, analysis in analyses.items():
        entries, raw_json, error = _refine_component(client, schema, analysis, feedback)
        if error is not None:
            logger.warning(
                "Refinement failed — component=%s (mantém análise atual)",
                analysis.component_name,
            )
            continue
        refined[component_id] = analysis.model_copy(
            update={
                "stride_entries": entries,
                "llm_reasoning": raw_json[:2000],
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        refined_count += 1

    logger.info(
        "Refinement completed — refined=%d/%d", refined_count, len(analyses)
    )

    return {
        "component_analyses": refined,
        "chat_history": chat_history,
        "hitl_feedback": None,
    }
