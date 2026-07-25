"""streamlit_app/stride_report.py

Helpers puros para renderizar o STRIDEReport na tela de relatório final
(US-3.2). `STRIDEReport.stride_matrix` (orchestration/models.py) é indexado
por categoria -> lista de component_id; para a tabela componente × categoria
pedida pelo Dev4 é mais simples derivar direto de `component_analyses`, sem
inverter esse dict."""
from __future__ import annotations

import html

_STRIDE_LETTERS = ["S", "T", "R", "I", "D", "E"]

_CATEGORY_COLORS = {
    "S": "#8e44ad",
    "T": "#2980b9",
    "R": "#16a085",
    "I": "#d35400",
    "D": "#c0392b",
    "E": "#7f8c8d",
}

_SEVERITY_COLORS = {
    "critical": "#a71d2a",
    "high": "#c0392b",
    "medium": "#8a6d00",
    "low": "#1e7e34",
}

# Ordem de exibição dos componentes na matriz STRIDE (US-3.2, notas técnicas).
_ELEMENT_TYPE_ORDER = ["process", "data_store", "data_flow", "external_entity"]


def category_badge_html(category: str) -> str:
    color = _CATEGORY_COLORS.get(category, "#555555")
    return f"<span style='background:{color};color:white;padding:1px 7px;border-radius:3px'>{category}</span>"


def severity_badge_html(severity: str) -> str:
    color = _SEVERITY_COLORS.get(severity, "#555555")
    label = html.escape(severity.upper())
    return f"<span style='background:{color};color:white;padding:1px 7px;border-radius:3px'>{label}</span>"


def sort_component_analyses(component_analyses: list[dict]) -> list[dict]:
    def _key(analysis: dict) -> tuple[int, str]:
        element_type = analysis.get("element_type", "")
        order = _ELEMENT_TYPE_ORDER.index(element_type) if element_type in _ELEMENT_TYPE_ORDER else len(_ELEMENT_TYPE_ORDER)
        return (order, analysis.get("component_name", ""))

    return sorted(component_analyses, key=_key)


def categories_present(analysis: dict) -> set[str]:
    return {entry["category"] for entry in analysis.get("stride_entries", [])}


def stride_matrix_html(component_analyses: list[dict]) -> str:
    """Tabela HTML componente × [S,T,R,I,D,E] (sem dependência de pandas)."""
    ordered = sort_component_analyses(component_analyses)

    header_cells = "".join(f"<th style='padding:4px 8px'>{letter}</th>" for letter in _STRIDE_LETTERS)
    rows = []
    for analysis in ordered:
        present = categories_present(analysis)
        cells = "".join(
            f"<td style='text-align:center;padding:4px 8px'>"
            f"{category_badge_html(letter) if letter in present else '–'}</td>"
            for letter in _STRIDE_LETTERS
        )
        component_name = html.escape(analysis.get("component_name", ""))
        rows.append(f"<tr><td style='padding:4px 8px'>{component_name}</td>{cells}</tr>")

    return (
        "<table style='width:100%;border-collapse:collapse'>"
        f"<thead><tr><th style='text-align:left;padding:4px 8px'>Componente</th>{header_cells}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def severity_counts(risk_summary: dict) -> dict[str, int]:
    return {severity: risk_summary.get(severity, 0) for severity in ("critical", "high", "medium", "low")}


def category_counts(risk_summary: dict) -> dict[str, int]:
    by_category = risk_summary.get("by_category", {})
    return {letter: by_category.get(letter, 0) for letter in _STRIDE_LETTERS}
