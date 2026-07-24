"""Testes do parser da resposta do LLM (US-2.4)."""
from __future__ import annotations

import json

import pytest

from orchestration.parser import STRIDEParsingError, parse_stride_entries

_VALID_ENTRY = {
    "category": "S",
    "threat_name": "Spoofing de token",
    "threat_description": "Falsificação de identidade.",
    "severity": "high",
    "mitigations": ["mTLS"],
    "source": "llm_only",
}


def test_array_json_valido():
    raw = json.dumps([_VALID_ENTRY])
    entries = parse_stride_entries(raw)
    assert len(entries) == 1
    assert entries[0].category == "S"
    assert entries[0].category_name == "Spoofing"  # derivado


def test_objeto_com_threats_desembrulhado():
    raw = json.dumps({"threats": [_VALID_ENTRY]})
    entries = parse_stride_entries(raw)
    assert len(entries) == 1


def test_bloco_json_markdown_extraido():
    raw = f"```json\n{json.dumps([_VALID_ENTRY])}\n```"
    entries = parse_stride_entries(raw)
    assert len(entries) == 1


def test_category_fora_do_literal_falha():
    bad = dict(_VALID_ENTRY, category="X")
    with pytest.raises(STRIDEParsingError):
        parse_stride_entries(json.dumps([bad]))


def test_objeto_sem_threats_falha():
    with pytest.raises(STRIDEParsingError):
        parse_stride_entries(json.dumps({"outra_coisa": []}))


def test_string_nao_json_falha():
    with pytest.raises(STRIDEParsingError):
        parse_stride_entries("isto não é json")
