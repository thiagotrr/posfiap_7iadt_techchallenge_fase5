"""Nó: generate_threats — gera as ameaças STRIDE do componente atual via LLM.

Usa `analyze_with_validation_retry` (retry de validação: 2 tentativas, reinjeta
o erro Pydantic no prompt). Retry de rede é interno ao LLMAnalysisClient.
Fallback final: stride_entries=[] com log WARNING — NUNCA aborta o grafo.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from orchestration.llm_client import LLMAnalysisClient, analyze_with_validation_retry
from orchestration.models import ComponentAnalysis
from orchestration.prompts import (
    STRIDE_ANALYSIS_SYSTEM_PROMPT,
    STRIDE_ANALYSIS_USER_TEMPLATE,
    stride_entries_json_schema,
)
from orchestration.state import GraphState
from orchestration.utils import build_component_profile, render_kg_context

logger = logging.getLogger(__name__)


def generate_threats(state: GraphState) -> dict:
    current_id = state["current_component_id"]
    component = next(c for c in state["diagram"].components if c.id == current_id)
    kg_result = state["kg_results"].get(current_id)

    schema = stride_entries_json_schema()
    user_prompt = STRIDE_ANALYSIS_USER_TEMPLATE.format(
        component_profile=build_component_profile(state["diagram"], current_id),
        kg_context=render_kg_context(kg_result) if kg_result else "",
        json_schema=json.dumps(schema, ensure_ascii=False),
    )

    client = LLMAnalysisClient()
    stride_entries, raw_json, error = analyze_with_validation_retry(
        client, STRIDE_ANALYSIS_SYSTEM_PROMPT, user_prompt, schema
    )

    analysis = ComponentAnalysis(
        component_id=component.id,
        component_name=component.name,
        element_type=component.element_type,
        cloud_service=component.aws_service,
        trust_boundary=component.trust_boundary,
        stride_entries=stride_entries,
        llm_reasoning=raw_json[:2000],
        analyzed_at=datetime.now(timezone.utc).isoformat(),
    )

    logger.info(
        "Generation completed — component=%s threats_found=%d",
        component.name, len(stride_entries),
    )

    updates: dict = {
        "component_analyses": {**state["component_analyses"], current_id: analysis}
    }
    if error is not None:
        logger.warning(
            "Generation failed — component=%s fallback=empty", component.name
        )
        updates["failed_component_ids"] = list(
            state.get("failed_component_ids", [])
        ) + [current_id]

    return updates
