"""Cliente de LLM para geração/refinamento STRIDE com structured output.

Duas camadas de retry DISTINTAS:
- Rede/rate-limit: tratada AQUI (3 tentativas, backoff exponencial). Esgotada →
  GenerationError.
- Validação (JSON/Pydantic): responsabilidade do CHAMADOR (generate_threats),
  NÃO deste cliente.

Providers configuráveis via ANALYSIS_LLM_PROVIDER. Nenhuma chave de API
hardcodada — os SDKs leem ANTHROPIC_API_KEY/OPENAI_API_KEY do ambiente.

Nota de wrapping: tool use (Anthropic) e response_format (OpenAI) exigem objeto
na raiz, mas stride_entries_json_schema() é um array. Envolvemos em
{"threats": <array>} e desembrulhamos pela chave "threats" antes de retornar —
analyze() sempre devolve a STRING JSON do array em si.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Optional

import anthropic
import openai

from orchestration.exceptions import GenerationError
from orchestration.models import STRIDEThreatEntry
from orchestration.parser import STRIDEParsingError, parse_stride_entries

logger = logging.getLogger(__name__)

ANALYSIS_LLM_PROVIDER = os.environ.get("ANALYSIS_LLM_PROVIDER", "anthropic")
ANALYSIS_LLM_TIMEOUT_S = float(os.environ.get("ANALYSIS_LLM_TIMEOUT_S", "90"))
_MAX_NETWORK_RETRIES = 3

# Pacing: intervalo mínimo (segundos) entre chamadas ao LLM, para respeitar o
# limite de requisições/minuto do provider (ex.: free tier do Gemini). 0 = sem
# pacing. Serializado por lock (seguro sob concorrência, ex.: threadpool FastAPI).
_MIN_INTERVAL_S = float(os.environ.get("ANALYSIS_LLM_MIN_INTERVAL_S", "0"))
_pace_lock = threading.Lock()
_last_call_monotonic = 0.0


def _respect_pacing() -> None:
    if _MIN_INTERVAL_S <= 0:
        return
    global _last_call_monotonic
    with _pace_lock:
        elapsed = time.monotonic() - _last_call_monotonic
        wait = _MIN_INTERVAL_S - elapsed
        if wait > 0:
            time.sleep(wait)
        _last_call_monotonic = time.monotonic()

# Defaults TEMPORÁRIOS (settings centralizadas do Dev 4 ainda não existem).
# Sobrescrevíveis por ambiente; nunca chamados nos testes (SDKs mockados).
_ANTHROPIC_MODEL = os.environ.get("ANALYSIS_ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
_OPENAI_MODEL = os.environ.get("ANALYSIS_OPENAI_MODEL", "gpt-4o-2024-08-06")
_MAX_TOKENS = int(os.environ.get("ANALYSIS_MAX_TOKENS", "4096"))

# Gemini via endpoint compatível com a API da OpenAI — reaproveita o cliente
# `openai` (sem nova dependência, mantém pydantic 2.9.2).
_GEMINI_MODEL = os.environ.get("ANALYSIS_GEMINI_MODEL", "gemini-flash-latest")
_GEMINI_BASE_URL = os.environ.get(
    "ANALYSIS_GEMINI_BASE_URL",
    "https://generativelanguage.googleapis.com/v1beta/openai/",
)
# Controle de raciocínio (OPCIONAL, opt-in). Vazio = não envia nada (compatível
# com todos os modelos). Se definido, envia reasoning_effort. ATENÇÃO: valores
# variam por modelo — "none" desliga o thinking no gemini-2.5-flash, mas causa
# 400 no gemini-3.x/flash-latest. Deixe vazio salvo se souber que o modelo aceita.
_GEMINI_REASONING_EFFORT = os.environ.get("ANALYSIS_GEMINI_REASONING_EFFORT", "").strip()

_TOOL_NAME = "submit_stride_threats"

# Exceções que justificam retry de rede (rate-limit, erro de servidor, conexão,
# timeout). RateLimitError/InternalServerError herdam de APIStatusError;
# APITimeoutError herda de APIConnectionError.
_RETRYABLE_ERRORS = (
    anthropic.APIStatusError,
    anthropic.APIConnectionError,
    openai.APIStatusError,
    openai.APIConnectionError,
)


def _wrap_object_schema(array_schema: dict, *, additional_properties_false: bool) -> dict:
    """Envolve um schema de array em objeto {"threats": <array>}.

    Hoista `$defs` para a raiz do objeto: os `$ref` gerados pelo Pydantic
    apontam para `#/$defs/...` (raiz do documento), então os defs precisam ficar
    no topo do schema enviado ao provider, não aninhados sob `threats`.
    """
    array = dict(array_schema)
    defs = array.pop("$defs", None)
    wrapper: dict = {
        "type": "object",
        "properties": {"threats": array},
        "required": ["threats"],
    }
    if additional_properties_false:
        wrapper["additionalProperties"] = False
    if defs is not None:
        wrapper["$defs"] = defs
    return wrapper


class LLMAnalysisClient:
    def __init__(self, provider: Optional[str] = None):
        self.provider = provider or ANALYSIS_LLM_PROVIDER

    def analyze(self, system_prompt: str, user_prompt: str, json_schema: dict) -> str:
        """Chama o LLM com structured output e retorna a STRING JSON do array
        de ameaças (já desembrulhada de {"threats": [...]}).

        Retry de rede/rate-limit interno (3 tentativas, backoff exponencial).
        NÃO faz retry de validação. Esgotadas as tentativas → GenerationError.
        """
        if self.provider == "anthropic":
            call = self._call_anthropic
        elif self.provider == "openai":
            call = self._call_openai
        elif self.provider == "gemini":
            call = self._call_gemini
        else:
            raise GenerationError(f"Provider de análise desconhecido: {self.provider!r}")

        last_exc: Optional[Exception] = None
        for attempt in range(_MAX_NETWORK_RETRIES):
            try:
                _respect_pacing()  # espaça chamadas p/ respeitar o RPM do provider
                return call(system_prompt, user_prompt, json_schema)
            except _RETRYABLE_ERRORS as exc:
                last_exc = exc
                logger.warning(
                    "LLM network retry — provider=%s attempt=%d/%d",
                    self.provider, attempt + 1, _MAX_NETWORK_RETRIES,
                )
                if attempt < _MAX_NETWORK_RETRIES - 1:
                    time.sleep(2 ** attempt)

        raise GenerationError(
            f"Falha de rede no LLM após {_MAX_NETWORK_RETRIES} tentativas "
            f"(provider={self.provider}): {last_exc}"
        )

    # ------------------------------------------------------------------
    # Providers
    # ------------------------------------------------------------------

    def _call_anthropic(self, system_prompt: str, user_prompt: str, json_schema: dict) -> str:
        client = anthropic.Anthropic(timeout=ANALYSIS_LLM_TIMEOUT_S)
        tool = {
            "name": _TOOL_NAME,
            "description": "Submete a lista de ameaças STRIDE identificadas.",
            "input_schema": _wrap_object_schema(json_schema, additional_properties_false=False),
        }
        response = client.messages.create(
            model=_ANTHROPIC_MODEL,
            max_tokens=_MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            tools=[tool],
            tool_choice={"type": "tool", "name": _TOOL_NAME},
        )
        self._log_usage(
            getattr(getattr(response, "usage", None), "input_tokens", None),
            getattr(getattr(response, "usage", None), "output_tokens", None),
        )
        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == _TOOL_NAME:
                return json.dumps(block.input["threats"])
        raise GenerationError("Resposta Anthropic sem bloco tool_use esperado")

    def _call_openai(self, system_prompt: str, user_prompt: str, json_schema: dict) -> str:
        client = openai.OpenAI(timeout=ANALYSIS_LLM_TIMEOUT_S)
        return self._call_openai_compatible(
            client, _OPENAI_MODEL, system_prompt, user_prompt, json_schema
        )

    def _call_gemini(self, system_prompt: str, user_prompt: str, json_schema: dict) -> str:
        # Gemini via endpoint OpenAI-compatível do Google. Reusa o cliente openai.
        client = openai.OpenAI(
            api_key=os.environ.get("GEMINI_API_KEY"),
            base_url=_GEMINI_BASE_URL,
            timeout=ANALYSIS_LLM_TIMEOUT_S,
        )
        extra_body = None
        if _GEMINI_REASONING_EFFORT:
            extra_body = {"reasoning_effort": _GEMINI_REASONING_EFFORT}
        return self._call_openai_compatible(
            client, _GEMINI_MODEL, system_prompt, user_prompt, json_schema, extra_body
        )

    def _call_openai_compatible(
        self, client, model: str, system_prompt: str, user_prompt: str,
        json_schema: dict, extra_body: Optional[dict] = None,
    ) -> str:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "stride_threats",
                    "schema": _wrap_object_schema(json_schema, additional_properties_false=True),
                    "strict": True,
                },
            },
            extra_body=extra_body,
        )
        usage = getattr(response, "usage", None)
        self._log_usage(
            getattr(usage, "prompt_tokens", None),
            getattr(usage, "completion_tokens", None),
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        return json.dumps(data["threats"])

    def _log_usage(self, input_tokens, output_tokens) -> None:
        # NUNCA logar conteúdo da resposta — apenas contagens/metadados.
        logger.info(
            "LLM usage — provider=%s input_tokens=%s output_tokens=%s",
            self.provider, input_tokens, output_tokens,
        )


_MAX_VALIDATION_RETRIES = 2  # tentativa inicial + 1 retry com o erro como contexto


def analyze_with_validation_retry(
    client: LLMAnalysisClient,
    system_prompt: str,
    user_prompt: str,
    json_schema: dict,
    max_retries: int = _MAX_VALIDATION_RETRIES,
) -> tuple[list[STRIDEThreatEntry], str, Exception | None]:
    """Chama o LLM com retry de VALIDAÇÃO (distinto do retry de rede interno).

    Em falha de validação (STRIDEParsingError), reinjeta o erro no prompt e tenta
    de novo. Em falha de rede (GenerationError, já esgotada internamente), não
    insiste. Retorna (entries, raw_json, last_error) — nunca levanta; o chamador
    decide o fallback (ex.: stride_entries=[]).
    """
    entries: list[STRIDEThreatEntry] = []
    raw_json = ""
    last_error: Exception | None = None
    prompt = user_prompt

    for attempt in range(max_retries):
        try:
            raw_json = client.analyze(system_prompt, prompt, json_schema)
            entries = parse_stride_entries(raw_json)
            return entries, raw_json, None
        except STRIDEParsingError as exc:
            last_error = exc
            prompt = (
                prompt
                + f"\n\nATENÇÃO: a resposta anterior falhou na validação: {exc}. "
                "Corrija e retorne APENAS o JSON válido."
            )
            logger.warning(
                "LLM validation retry — attempt=%d/%d", attempt + 1, max_retries
            )
        except GenerationError as exc:
            return entries, raw_json, exc

    return entries, raw_json, last_error
