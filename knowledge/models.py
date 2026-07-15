"""
knowledge/models.py

Modelos Pydantic v2 para os resultados de query do Knowledge Graph STRIDE.
Estes modelos são o contrato público consumido por Dev 3 (LangGraph) e Dev 4 (FastAPI).
"""

from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


class ThreatResult(BaseModel):
    """Ameaça canônica recuperada do KG."""
    id: str = Field(description="Identificador único da ameaça no KG.")
    name: str = Field(description="Nome curto da ameaça (ex: 'Session Hijacking').")
    description: str = Field(description="Descrição detalhada da ameaça no contexto STRIDE.")
    severity: Literal["critical", "high", "medium", "low"] = Field(
        description="Severidade estimada da ameaça."
    )


class MitigationResult(BaseModel):
    """Mitigação canônica recuperada do KG."""
    id: str = Field(description="Identificador único da mitigação no KG.")
    name: str = Field(description="Nome curto da mitigação.")
    description: str = Field(description="Descrição da medida de controle.")
    control_type: Literal["preventive", "detective", "corrective"] = Field(
        description="Tipo de controle de segurança."
    )


class STRIDEResult(BaseModel):
    """Resultado de uma categoria STRIDE para um tipo de elemento."""
    category: str = Field(description="Nome completo da categoria (ex: 'Spoofing').")
    letter: str = Field(description="Letra STRIDE (S/T/R/I/D/E).")
    threats: list[ThreatResult] = Field(default_factory=list)
    mitigations: list[MitigationResult] = Field(default_factory=list)


class KGQueryResult(BaseModel):
    """
    Resultado completo de uma query ao Knowledge Graph STRIDE.
    É o objeto de estado que o nó de retrieval do LangGraph (Dev 3) recebe
    e passa para o nó de geração de ameaças.
    """
    element_type: str = Field(
        description="Tipo de elemento STRIDE (process/data_store/data_flow/external_entity)."
    )
    cloud_service: Optional[str] = Field(
        default=None,
        description="Nome do serviço de nuvem consultado (ex: 'RDS', 'S3'). None = apenas taxonomia.",
    )
    stride_results: list[STRIDEResult] = Field(
        default_factory=list,
        description="Lista de resultados por categoria STRIDE aplicável.",
    )
    total_threats: int = Field(
        default=0,
        description="Total de ameaças encontradas (soma de todas as categorias).",
    )
    query_source: Literal["taxonomy", "enriched", "both"] = Field(
        description=(
            "'taxonomy' = apenas taxonomia estática; "
            "'enriched' = apenas dados do crawler; "
            "'both' = ambas as fontes."
        )
    )

    def model_post_init(self, __context) -> None:  # noqa: ANN001
        # Garante consistência do total_threats ao desserializar
        if self.total_threats == 0 and self.stride_results:
            object.__setattr__(
                self,
                "total_threats",
                sum(len(r.threats) for r in self.stride_results),
            )
