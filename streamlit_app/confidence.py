"""streamlit_app/confidence.py

Badge de confiança da extração (US-2.3). `extraction_confidence` é texto
livre (ver extraction/schemas.py::DiagramMetadata), não um enum -- o match é
por substring case-insensitive, checando "alta" antes de "média" antes de
"baixa"."""
from __future__ import annotations

import html

_COLORS = {
    "alta": "#1e7e34",
    "média": "#8a6d00",
    "baixa": "#a71d2a",
}
_NEUTRAL_COLOR = "#555555"


def confidence_level(extraction_confidence: str) -> str | None:
    """Retorna "alta"/"média"/"baixa" se o texto contiver um desses termos
    (case-insensitive), ou None se não reconhecido. Usado tanto pelo badge
    colorido quanto pelo gate de confiança baixa em 02_extraction_review.py
    -- mantém as duas checagens sincronizadas com a mesma convenção."""
    lowered = extraction_confidence.lower()
    for label in _COLORS:
        if label in lowered:
            return label
    return None


def confidence_badge_html(extraction_confidence: str) -> str:
    level = confidence_level(extraction_confidence)
    color = _COLORS[level] if level else _NEUTRAL_COLOR
    display_text = level.upper() if level else html.escape(extraction_confidence)

    return (
        f"<span style='background:{color};color:white;padding:2px 8px;"
        f"border-radius:3px'>{display_text}</span>"
    )


def attention_marker(confidence: float | None, note: str | None) -> str:
    """Retorna um aviso "⚠️ ..." se o item (componente ou fluxo de dados)
    tiver uma nota do extrator ou confiança de detecção baixa (< 0.7), ou
    string vazia se estiver ok. A nota tem prioridade sobre a confiança
    quando os dois estão presentes -- é o motivo mais específico."""
    if note:
        return f"⚠️ {note}"
    if confidence is not None and confidence < 0.7:
        return f"⚠️ confiança baixa ({confidence:.0%})"
    return ""
