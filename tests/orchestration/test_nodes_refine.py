"""Testes do nó refine_analysis — refinamento via LLM (US-3.2, Épico 3).

Mock em LLMAnalysisClient.analyze (nenhuma chamada real de rede).
"""
from __future__ import annotations

import json
import logging
from unittest.mock import patch

from orchestration.exceptions import GenerationError
from orchestration.llm_client import LLMAnalysisClient
from orchestration.models import ComponentAnalysis, STRIDEThreatEntry
from orchestration.nodes import refine_analysis


def _analysis(component_id="c1", category="S", threat="Ameaça original"):
    return ComponentAnalysis(
        component_id=component_id,
        component_name=f"Comp {component_id}",
        element_type="process",
        cloud_service="Lambda",
        trust_boundary="tb",
        stride_entries=[
            STRIDEThreatEntry(
                category=category,
                threat_name=threat,
                threat_description="desc",
                severity="medium",
                mitigations=["m"],
                source="llm_only",
            )
        ],
        llm_reasoning="original",
        analyzed_at="2026-07-21T00:00:00Z",
    )


def _state(feedback="detalhar melhor", n=1):
    analyses = {f"c{i}": _analysis(f"c{i}") for i in range(1, n + 1)}
    return {
        "hitl_feedback": feedback,
        "chat_history": [],
        "component_analyses": analyses,
    }


_REFINED_JSON = json.dumps(
    [
        {
            "category": "T",
            "threat_name": "Ameaça refinada",
            "threat_description": "nova desc",
            "severity": "high",
            "mitigations": ["nova mitigação"],
            "source": "llm_only",
        }
    ]
)


def test_refina_e_substitui_entries():
    with patch.object(LLMAnalysisClient, "analyze", return_value=_REFINED_JSON) as m:
        result = refine_analysis(_state(feedback="focar em tampering"))

    analysis = result["component_analyses"]["c1"]
    assert analysis.stride_entries[0].category == "T"
    assert analysis.stride_entries[0].threat_name == "Ameaça refinada"
    assert result["hitl_feedback"] is None
    assert result["chat_history"][-1] == {"role": "user", "content": "focar em tampering"}
    assert m.call_count == 1


def test_refina_todos_os_componentes():
    with patch.object(LLMAnalysisClient, "analyze", return_value=_REFINED_JSON) as m:
        result = refine_analysis(_state(n=3))
    assert m.call_count == 3
    for cid in ("c1", "c2", "c3"):
        assert result["component_analyses"][cid].stride_entries[0].category == "T"


def test_prompt_de_refinamento_contem_feedback_e_analise_atual():
    with patch.object(LLMAnalysisClient, "analyze", return_value=_REFINED_JSON) as m:
        refine_analysis(_state(feedback="remover falsos positivos"))
    # analyze(system, user, schema): user é args[1]
    user_prompt = m.call_args.args[1]
    assert "remover falsos positivos" in user_prompt
    assert "Ameaça original" in user_prompt  # a análise atual foi injetada


def test_falha_de_refinamento_mantem_analise_atual(caplog):
    with patch.object(LLMAnalysisClient, "analyze", side_effect=GenerationError("rede")):
        with caplog.at_level(logging.WARNING):
            result = refine_analysis(_state(feedback="algo"))

    analysis = result["component_analyses"]["c1"]
    # análise original preservada (não virou vazia nem quebrou)
    assert analysis.stride_entries[0].threat_name == "Ameaça original"
    assert "Refinement failed" in " ".join(r.getMessage() for r in caplog.records)


def test_sem_feedback_nao_chama_llm():
    state = {"hitl_feedback": None, "chat_history": [], "component_analyses": {"c1": _analysis()}}
    with patch.object(LLMAnalysisClient, "analyze") as m:
        result = refine_analysis(state)
    m.assert_not_called()
    assert result["hitl_feedback"] is None
    # sem feedback, refine não mexe nas análises (não as retorna).
    assert "component_analyses" not in result
