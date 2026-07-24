"""Estimativa de custo de tokens da análise (dry-run — NÃO chama o LLM).

Endereça o risco "custo de tokens elevado (14 chamadas por análise)" do CLAUDE.md:
permite dimensionar o custo de uma análise antes de executá-la, montando os
mesmos prompts que o nó de geração usaria e estimando os tokens de entrada.

A estimativa é heurística (~4 caracteres por token) — sem dependência de
tokenizer nem chamada de rede. Serve para ordem de grandeza / orçamento.
"""
from __future__ import annotations

import json

from extraction.schemas import ArchitectureDiagram
from orchestration.prompts import (
    STRIDE_ANALYSIS_SYSTEM_PROMPT,
    STRIDE_ANALYSIS_USER_TEMPLATE,
    stride_entries_json_schema,
)
from orchestration.utils import build_component_profile, render_kg_context

_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Estimativa heurística de tokens de um texto (~4 chars/token, mínimo 1)."""
    return max(1, (len(text) + _CHARS_PER_TOKEN - 1) // _CHARS_PER_TOKEN)


def estimate_analysis_tokens(diagram: ArchitectureDiagram) -> dict:
    """Estima os tokens de ENTRADA da análise, por componente e no total.

    Usa os fixtures do KG (aproximação, enquanto o Neo4j real do Dev 2 não está
    disponível). Não chama o LLM.
    """
    from knowledge.fixtures import get_fixture_for  # import tardio (stub Dev 2)

    schema_str = json.dumps(stride_entries_json_schema(), ensure_ascii=False)
    system_tokens = estimate_tokens(STRIDE_ANALYSIS_SYSTEM_PROMPT)

    per_component: list[dict] = []
    total = 0
    for component in diagram.components:
        profile = build_component_profile(diagram, component.id)
        try:
            kg_context = render_kg_context(get_fixture_for(component.element_type))
        except KeyError:
            kg_context = ""
        user_prompt = STRIDE_ANALYSIS_USER_TEMPLATE.format(
            component_profile=profile,
            kg_context=kg_context,
            json_schema=schema_str,
        )
        tokens = system_tokens + estimate_tokens(user_prompt)
        per_component.append(
            {
                "component_id": component.id,
                "name": component.name,
                "input_tokens": tokens,
            }
        )
        total += tokens

    return {
        "components": len(diagram.components),
        "total_input_tokens": total,
        "per_component": per_component,
        "note": "estimativa heurística (~4 chars/token), sem chamada de LLM",
    }
