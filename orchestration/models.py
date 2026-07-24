"""Modelos de output do grafo de orquestração STRIDE (Pydantic v2).

Estes modelos são o contrato de saída consumido pelo Dev 4 (FastAPI) e pelo
Streamlit. Serialização JSON consistente via `model_dump()` / `model_validate()`.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, model_validator

# Nomes canônicos das 6 categorias STRIDE (Microsoft). Fonte única para derivar
# `category_name` a partir de `category`.
_STRIDE_CATEGORY_NAMES: dict[str, str] = {
    "S": "Spoofing",
    "T": "Tampering",
    "R": "Repudiation",
    "I": "Information Disclosure",
    "D": "Denial of Service",
    "E": "Elevation of Privilege",
}


class STRIDEThreatEntry(BaseModel):
    """Uma ameaça STRIDE contextualizada para um componente específico."""

    category: Literal["S", "T", "R", "I", "D", "E"]
    # `category_name` NUNCA é fonte de verdade: é sempre derivado de `category`
    # pelo validator abaixo. O LLM não precisa mantê-lo sincronizado — no Épico 2
    # ele pode ser removido do JSON Schema injetado no prompt (reduz o tamanho do
    # schema enviado), pois é preenchido automaticamente após o parse.
    category_name: str = ""
    threat_name: str
    threat_description: str
    severity: Literal["critical", "high", "medium", "low"]
    mitigations: list[str]
    source: Literal["taxonomy", "enriched", "both", "llm_only"]

    @model_validator(mode="after")
    def _derive_category_name(self) -> "STRIDEThreatEntry":
        self.category_name = _STRIDE_CATEGORY_NAMES[self.category]
        return self


class ComponentAnalysis(BaseModel):
    """Análise STRIDE completa de um único componente do diagrama."""

    component_id: str
    component_name: str
    element_type: str
    cloud_service: Optional[str] = None
    trust_boundary: str
    stride_entries: list[STRIDEThreatEntry]
    llm_reasoning: str
    analyzed_at: str


class STRIDEReport(BaseModel):
    """Relatório final consolidado de toda a análise STRIDE do diagrama."""

    diagram_provider: str
    total_components: int
    total_threats: int
    generated_at: str
    component_analyses: list[ComponentAnalysis]
    stride_matrix: dict[str, list[str]]
    risk_summary: dict


class GraphStateResponse(BaseModel):
    """Visão serializável do estado do grafo para polling via API (Dev 4)."""

    thread_id: str
    status: Literal["running", "hitl_pending", "completed", "error"]
    components_analyzed_count: int
    components_total: int
    # Ids dos componentes já analisados (a UI do Dev 4 precisa da lista, não só
    # da contagem). Default [] para não quebrar quem já instancia o modelo.
    analyzed_component_ids: list[str] = []
    # Componentes cuja geração caiu no fallback stride_entries=[] (JSON inválido
    # após retries). Distingue "sem ameaças" de "falha silenciosa" — evita
    # inflar a métrica de sucesso do MVP. Default 0.
    components_failed_count: int = 0
    hitl_summary: Optional[list[dict]] = None
    report: Optional[STRIDEReport] = None
