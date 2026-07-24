"""Testes da estimativa de tokens dry-run (US-4.4, Épico 4)."""
from __future__ import annotations

from orchestration.cost import estimate_analysis_tokens, estimate_tokens
from orchestration.fixtures import example_diagram


def test_estimate_tokens_heuristica():
    assert estimate_tokens("") == 1          # mínimo 1
    assert estimate_tokens("abcd") == 1      # 4 chars -> 1 token
    assert estimate_tokens("a" * 40) == 10   # 40 chars -> 10 tokens


def test_estimate_analysis_tokens_exemplo():
    est = estimate_analysis_tokens(example_diagram())
    assert est["components"] == 2
    assert est["total_input_tokens"] > 0
    assert len(est["per_component"]) == 2
    assert all(c["input_tokens"] > 0 for c in est["per_component"])
    # o total é a soma das partes
    assert est["total_input_tokens"] == sum(
        c["input_tokens"] for c in est["per_component"]
    )
