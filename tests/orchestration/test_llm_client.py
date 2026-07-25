"""Testes do LLMAnalysisClient — structured output + retry de rede (US-2.4).

Todos os SDKs são mockados: NENHUMA chamada real de rede ocorre.
"""
from __future__ import annotations

import json
import logging
from types import SimpleNamespace
from unittest.mock import patch

import anthropic
import httpx
import pytest

from orchestration.exceptions import GenerationError
from orchestration.llm_client import LLMAnalysisClient, analyze_with_validation_retry
from orchestration.parser import STRIDEParsingError
from orchestration.prompts import stride_entries_json_schema

_ENTRY = {
    "category": "S",
    "threat_name": "Spoofing",
    "threat_description": "descrição sensível que não deve vazar no log",
    "severity": "high",
    "mitigations": ["mTLS"],
    "source": "llm_only",
}


def _rate_limit_error() -> anthropic.RateLimitError:
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    resp = httpx.Response(429, request=req)
    return anthropic.RateLimitError("rate limited", response=resp, body=None)


def _anthropic_response(input_tokens=10, output_tokens=20):
    block = SimpleNamespace(
        type="tool_use", name="submit_stride_threats", input={"threats": [_ENTRY]}
    )
    usage = SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens)
    return SimpleNamespace(content=[block], usage=usage)


def _openai_response():
    msg = SimpleNamespace(content=json.dumps({"threats": [_ENTRY]}))
    choice = SimpleNamespace(message=msg)
    usage = SimpleNamespace(prompt_tokens=5, completion_tokens=7)
    return SimpleNamespace(choices=[choice], usage=usage)


def _schema() -> dict:
    return stride_entries_json_schema()


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------


def test_anthropic_sucesso_extrai_json():
    with patch("orchestration.llm_client.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _anthropic_response()
        client = LLMAnalysisClient(provider="anthropic")
        raw = client.analyze("sys", "user", _schema())

    parsed = json.loads(raw)
    assert isinstance(parsed, list)
    assert parsed[0]["category"] == "S"


def test_anthropic_retry_rede_sucesso_na_terceira():
    with patch("orchestration.llm_client.anthropic.Anthropic") as MockClient, \
         patch("orchestration.llm_client.time.sleep") as mock_sleep:
        MockClient.return_value.messages.create.side_effect = [
            _rate_limit_error(),
            _rate_limit_error(),
            _anthropic_response(),
        ]
        client = LLMAnalysisClient(provider="anthropic")
        raw = client.analyze("sys", "user", _schema())

    assert json.loads(raw)[0]["category"] == "S"
    assert MockClient.return_value.messages.create.call_count == 3
    assert mock_sleep.call_count == 2  # 2 backoffs entre as 3 tentativas


def test_anthropic_falha_rede_esgota_retries():
    with patch("orchestration.llm_client.anthropic.Anthropic") as MockClient, \
         patch("orchestration.llm_client.time.sleep"):
        MockClient.return_value.messages.create.side_effect = _rate_limit_error()
        client = LLMAnalysisClient(provider="anthropic")
        with pytest.raises(GenerationError):
            client.analyze("sys", "user", _schema())
        assert MockClient.return_value.messages.create.call_count == 3


def test_usage_logado_sem_conteudo(caplog):
    with patch("orchestration.llm_client.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _anthropic_response()
        client = LLMAnalysisClient(provider="anthropic")
        with caplog.at_level(logging.INFO):
            client.analyze("sys", "user", _schema())

    mensagens = " ".join(rec.getMessage() for rec in caplog.records)
    assert "LLM usage" in mensagens
    assert "input_tokens=10" in mensagens
    assert "output_tokens=20" in mensagens
    # Conteúdo da resposta NUNCA deve aparecer nos logs.
    assert "descrição sensível" not in mensagens


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------


def test_openai_sucesso_extrai_json():
    with patch("orchestration.llm_client.openai.OpenAI") as MockClient:
        MockClient.return_value.chat.completions.create.return_value = _openai_response()
        client = LLMAnalysisClient(provider="openai")
        raw = client.analyze("sys", "user", _schema())

    parsed = json.loads(raw)
    assert isinstance(parsed, list)
    assert parsed[0]["category"] == "S"
    # Confirma que response_format foi montado com o wrapper objeto {"threats":...}.
    _, kwargs = MockClient.return_value.chat.completions.create.call_args
    schema_enviado = kwargs["response_format"]["json_schema"]["schema"]
    assert schema_enviado["type"] == "object"
    assert "threats" in schema_enviado["properties"]
    assert schema_enviado["required"] == ["threats"]


# ---------------------------------------------------------------------------
# Gemini (via endpoint OpenAI-compatível)
# ---------------------------------------------------------------------------


def test_gemini_sucesso_aponta_endpoint_sem_reasoning_por_default():
    with patch("orchestration.llm_client.openai.OpenAI") as MockClient:
        MockClient.return_value.chat.completions.create.return_value = _openai_response()
        client = LLMAnalysisClient(provider="gemini")
        raw = client.analyze("sys", "user", _schema())

    assert json.loads(raw)[0]["category"] == "S"
    # cliente apontou para o endpoint OpenAI-compatível do Gemini
    assert "generativelanguage.googleapis.com" in MockClient.call_args.kwargs["base_url"]
    # por default NÃO envia reasoning_effort (compatível com todos os modelos)
    _, kwargs = MockClient.return_value.chat.completions.create.call_args
    assert kwargs["extra_body"] is None


def test_gemini_envia_reasoning_effort_quando_configurado(monkeypatch):
    monkeypatch.setattr(
        "orchestration.llm_client._GEMINI_REASONING_EFFORT", "none"
    )
    with patch("orchestration.llm_client.openai.OpenAI") as MockClient:
        MockClient.return_value.chat.completions.create.return_value = _openai_response()
        LLMAnalysisClient(provider="gemini").analyze("sys", "user", _schema())

    _, kwargs = MockClient.return_value.chat.completions.create.call_args
    assert kwargs["extra_body"] == {"reasoning_effort": "none"}


# ---------------------------------------------------------------------------
# Pacing (intervalo mínimo entre chamadas)
# ---------------------------------------------------------------------------


def test_pacing_dorme_o_restante_do_intervalo(monkeypatch):
    import orchestration.llm_client as mod

    monkeypatch.setattr(mod, "_MIN_INTERVAL_S", 10.0)
    monkeypatch.setattr(mod, "_last_call_monotonic", 100.0)
    sleeps = []
    monkeypatch.setattr(mod.time, "sleep", lambda s: sleeps.append(s))
    # now=105 (elapsed=5 → espera 5); depois monotonic=110 para registrar o último.
    monkeypatch.setattr(mod.time, "monotonic", iter([105.0, 110.0]).__next__)

    mod._respect_pacing()
    assert sleeps == [5.0]


def test_pacing_desligado_nao_dorme(monkeypatch):
    import orchestration.llm_client as mod

    monkeypatch.setattr(mod, "_MIN_INTERVAL_S", 0.0)
    sleeps = []
    monkeypatch.setattr(mod.time, "sleep", lambda s: sleeps.append(s))

    mod._respect_pacing()
    assert sleeps == []


# ---------------------------------------------------------------------------
# Resposta malformada — deve virar STRIDEParsingError (retry de validação +
# fallback por-componente), NUNCA exceção crua que aborta o grafo.
# ---------------------------------------------------------------------------


def _openai_response_content(content):
    """Resposta OpenAI/Gemini com um `content` arbitrário (inclusive None)."""
    msg = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=msg)
    usage = SimpleNamespace(prompt_tokens=5, completion_tokens=7)
    return SimpleNamespace(choices=[choice], usage=usage)


@pytest.mark.parametrize(
    "content, motivo",
    [
        ("desculpe, não posso ajudar com isso", "recusa em texto (não é JSON)"),
        (None, "content=None (recusa dura do provider)"),
        (json.dumps({"foo": 1}), "JSON válido mas sem a chave 'threats'"),
        ("{isto não é json", "JSON truncado/inválido"),
    ],
)
def test_openai_resposta_malformada_vira_parsing_error(content, motivo):
    with patch("orchestration.llm_client.openai.OpenAI") as MockClient:
        MockClient.return_value.chat.completions.create.return_value = (
            _openai_response_content(content)
        )
        client = LLMAnalysisClient(provider="openai")
        with pytest.raises(STRIDEParsingError):
            client.analyze("sys", "user", _schema())


def test_anthropic_tool_input_sem_threats_vira_parsing_error():
    block = SimpleNamespace(
        type="tool_use", name="submit_stride_threats", input={"errado": []}
    )
    resp = SimpleNamespace(
        content=[block], usage=SimpleNamespace(input_tokens=1, output_tokens=1)
    )
    with patch("orchestration.llm_client.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = resp
        client = LLMAnalysisClient(provider="anthropic")
        with pytest.raises(STRIDEParsingError):
            client.analyze("sys", "user", _schema())


def test_validation_retry_absorve_malformado_sem_abortar():
    # A garantia central da correção: resposta malformada NÃO propaga exceção
    # crua — vira retry de validação e, esgotado, fallback (entries=[] +
    # last_error). É isso que impede 1 componente de derrubar os 14.
    with patch("orchestration.llm_client.openai.OpenAI") as MockClient:
        MockClient.return_value.chat.completions.create.return_value = (
            _openai_response_content("não é json")
        )
        client = LLMAnalysisClient(provider="openai")
        entries, raw, error = analyze_with_validation_retry(
            client, "sys", "user", _schema()
        )

    assert entries == []
    assert isinstance(error, STRIDEParsingError)
    # 2 tentativas de validação (inicial + 1 retry) foram feitas.
    assert MockClient.return_value.chat.completions.create.call_count == 2
