"""Testes do nó generate_threats — retry de validação + fallback (US-2.4).

Mock no nível de LLMAnalysisClient.analyze (interface do nó), não nos SDKs.
"""
from __future__ import annotations

import json
import logging
from unittest.mock import patch

from extraction.schemas import (
    ArchitectureDiagram,
    Component,
    DataFlow,
    DiagramMetadata,
    TrustBoundary,
)
from orchestration.exceptions import GenerationError
from orchestration.llm_client import LLMAnalysisClient
from orchestration.nodes import generate_threats


def _entry(description="Falsificação de identidade."):
    return {
        "category": "S",
        "threat_name": "Spoofing",
        "threat_description": description,
        "severity": "high",
        "mitigations": ["mTLS"],
        "source": "llm_only",
    }


def _state() -> dict:
    diagram = ArchitectureDiagram(
        diagram_metadata=DiagramMetadata(
            cloud_provider="aws", region=None, extraction_confidence="alta"
        ),
        trust_boundaries=[TrustBoundary(id="tb", name="B", type="vpc", parent=None)],
        components=[
            Component(
                id="c1", name="Gateway", aws_service="API Gateway",
                element_type="process", category=None, trust_boundary="tb",
                instance_count=1,
            )
        ],
        data_flows=[
            DataFlow(
                id="f1", source="c1", destination="c1", protocol="x",
                crosses_boundary=False, note=None,
            )
        ],
    )
    return {
        "diagram": diagram,
        "current_component_id": "c1",
        "kg_results": {},
        "component_analyses": {},
    }


def test_sucesso_primeira_tentativa_com_truncamento():
    raw = json.dumps([_entry(description="x" * 3000)])  # > 2000 chars
    with patch.object(LLMAnalysisClient, "analyze", return_value=raw) as m:
        result = generate_threats(_state())

    analysis = result["component_analyses"]["c1"]
    assert len(analysis.stride_entries) == 1
    assert analysis.stride_entries[0].category == "S"
    assert len(analysis.llm_reasoning) == 2000  # truncado
    assert m.call_count == 1


def test_invalida_depois_valida_reenvia_erro_como_contexto():
    valido = json.dumps([_entry()])
    with patch.object(
        LLMAnalysisClient, "analyze", side_effect=["resposta inválida", valido]
    ) as m:
        result = generate_threats(_state())

    analysis = result["component_analyses"]["c1"]
    assert len(analysis.stride_entries) == 1
    assert m.call_count == 2
    # O user_prompt da 2ª chamada deve conter o erro da 1ª como contexto.
    segundo_user_prompt = m.call_args_list[1].args[1]
    assert "ATENÇÃO" in segundo_user_prompt
    assert "falhou na validação" in segundo_user_prompt


def test_invalida_nas_duas_tentativas_fallback_vazio(caplog):
    with patch.object(
        LLMAnalysisClient, "analyze", side_effect=["lixo", "mais lixo"]
    ) as m:
        with caplog.at_level(logging.WARNING):
            result = generate_threats(_state())

    analysis = result["component_analyses"]["c1"]
    assert analysis.stride_entries == []  # fallback
    assert m.call_count == 2
    mensagens = " ".join(rec.getMessage() for rec in caplog.records)
    assert "Generation failed" in mensagens


def test_generation_error_de_rede_nao_retenta_validacao():
    with patch.object(
        LLMAnalysisClient, "analyze", side_effect=GenerationError("falha de rede")
    ) as m:
        result = generate_threats(_state())

    analysis = result["component_analyses"]["c1"]
    assert analysis.stride_entries == []
    assert m.call_count == 1  # não re-tenta validação após erro de rede
