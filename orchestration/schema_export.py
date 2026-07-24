"""Exportação do snapshot JSON Schema do contrato de saída (para Dev 4).

`generate_schemas_v1()` é a fonte única do conteúdo de `schemas_v1.json`. O
arquivo commitado é regenerado por `scripts/gen_schemas.py` e validado por teste
de snapshot (detecta drift entre os modelos Pydantic e o contrato publicado).
"""
from __future__ import annotations

from orchestration.models import GraphStateResponse, STRIDEReport

SCHEMA_VERSION = "v1"


def generate_schemas_v1() -> dict:
    """Retorna o dict do contrato: JSON Schema de STRIDEReport e GraphStateResponse."""
    return {
        "version": SCHEMA_VERSION,
        "$comment": (
            "Contrato de saída da orquestração STRIDE (Dev 3 → Dev 4). "
            "Gerado a partir de orchestration.models — não editar à mão."
        ),
        "STRIDEReport": STRIDEReport.model_json_schema(),
        "GraphStateResponse": GraphStateResponse.model_json_schema(),
    }
