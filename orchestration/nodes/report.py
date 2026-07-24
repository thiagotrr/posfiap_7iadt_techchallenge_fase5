"""Nó: generate_report — consolida o STRIDEReport final.

Agregação real: matriz STRIDE, resumo de risco enriquecido (por severidade, por
categoria, cobertura e falhas) e ordenação das ameaças por severidade dentro de
cada componente. Mantém as chaves de severidade em `risk_summary` (compat).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from orchestration.models import STRIDEReport
from orchestration.state import GraphState

logger = logging.getLogger(__name__)

# Categorias STRIDE canônicas (Microsoft). Chaves da stride_matrix.
_STRIDE_LETTERS = ["S", "T", "R", "I", "D", "E"]

# Ordem de prioridade das severidades (crítico primeiro).
_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _sort_by_severity(entries):
    return sorted(entries, key=lambda e: _SEVERITY_ORDER.get(e.severity, 99))


def generate_report(state: GraphState) -> dict:
    analyses = list(state["component_analyses"].values())
    failed_ids = state.get("failed_component_ids", [])

    stride_matrix: dict[str, list[str]] = {letter: [] for letter in _STRIDE_LETTERS}
    by_category: dict[str, int] = {letter: 0 for letter in _STRIDE_LETTERS}
    severity_counts: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    total_threats = 0
    components_with_threats = 0

    ordered_analyses = []
    for analysis in analyses:
        sorted_entries = _sort_by_severity(analysis.stride_entries)
        ordered_analyses.append(
            analysis.model_copy(update={"stride_entries": sorted_entries})
        )
        if sorted_entries:
            components_with_threats += 1
        for entry in sorted_entries:
            total_threats += 1
            if entry.category in stride_matrix:
                if analysis.component_id not in stride_matrix[entry.category]:
                    stride_matrix[entry.category].append(analysis.component_id)
                by_category[entry.category] += 1
            if entry.severity in severity_counts:
                severity_counts[entry.severity] += 1

    total_components = len(analyses)
    risk_summary = {
        # contagem por severidade (mantida para compatibilidade)
        **severity_counts,
        "total_threats": total_threats,
        "by_category": by_category,
        "components_analyzed": total_components,
        "components_with_threats": components_with_threats,
        "components_without_threats": total_components - components_with_threats,
        "components_failed": len(failed_ids),
    }

    report = STRIDEReport(
        diagram_provider=state["diagram"].diagram_metadata.cloud_provider,
        total_components=total_components,
        total_threats=total_threats,
        generated_at=datetime.now(timezone.utc).isoformat(),
        component_analyses=ordered_analyses,
        stride_matrix=stride_matrix,
        risk_summary=risk_summary,
    )

    logger.info(
        "generate_report — components=%d threats=%d with_threats=%d failed=%d",
        total_components, total_threats, components_with_threats, len(failed_ids),
    )

    return {"report": report}
