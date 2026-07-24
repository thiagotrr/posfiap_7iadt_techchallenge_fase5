"""Exceções do módulo de orquestração.

Sem lógica extra por enquanto — apenas os tipos para uso pelos nós do grafo.
"""
from __future__ import annotations


class RetrievalError(Exception):
    """Falha ao recuperar ameaças do Knowledge Graph."""


class GenerationError(Exception):
    """Falha na geração de ameaças STRIDE via LLM."""


class HITLAbortedError(Exception):
    """Sessão Human-in-the-Loop abortada pelo usuário."""


class ReportGenerationError(Exception):
    """Falha ao consolidar o STRIDEReport final."""
