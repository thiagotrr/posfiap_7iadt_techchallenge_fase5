"""Parser da resposta estruturada do LLM para list[STRIDEThreatEntry].

Robusto a duas formas de entrada: array JSON solto (o que analyze() retorna) ou
objeto {"threats": [...]}. Extrai bloco ```json se presente (mesmo padrão de
extraction/parser.py do Dev 1). Qualquer falha vira STRIDEParsingError, cuja
mensagem alimenta o retry com contexto em generate_threats.
"""
from __future__ import annotations

import json
import re

from pydantic import TypeAdapter, ValidationError

from orchestration.models import STRIDEThreatEntry

_ADAPTER = TypeAdapter(list[STRIDEThreatEntry])
_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


class STRIDEParsingError(Exception):
    """JSON inválido ou falha de validação Pydantic ao parsear a resposta do LLM.

    Contém a mensagem de erro original para uso no retry com contexto adicional.
    """


def parse_stride_entries(raw_json: str) -> list[STRIDEThreatEntry]:
    text = (raw_json or "").strip()

    match = _JSON_BLOCK_RE.search(text)
    if match:
        text = match.group(1).strip()

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        raise STRIDEParsingError(f"JSON malformado: {exc}") from exc

    # Desembrulha {"threats": [...]} se vier como objeto.
    if isinstance(data, dict):
        if "threats" not in data:
            raise STRIDEParsingError("Chave 'threats' ausente no objeto JSON.")
        data = data["threats"]

    try:
        return _ADAPTER.validate_python(data)
    except ValidationError as exc:
        raise STRIDEParsingError(f"Validação Pydantic falhou: {exc}") from exc
