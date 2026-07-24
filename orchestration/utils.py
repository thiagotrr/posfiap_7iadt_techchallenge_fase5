"""Helpers puros da orquestração — sem dependência de LLM, Neo4j ou rede.

Usados para montar o contexto textual que alimenta os prompts STRIDE (Épico 2).
`crosses_boundary` é derivado dos DataFlow do diagrama, contextualizando o risco
sem intervenção manual.
"""
from __future__ import annotations

from extraction.schemas import ArchitectureDiagram
from knowledge.models import KGQueryResult

# Limite de caracteres do contexto do KG injetado no prompt (controla custo de
# tokens — ver CLAUDE.md, "Custo de tokens é real").
_KG_CONTEXT_MAX_CHARS = 6000


def component_crosses_boundary(diagram: ArchitectureDiagram, component_id: str) -> bool:
    """True se o componente é origem ou destino de algum DataFlow que cruza
    fronteira de confiança (crosses_boundary=True)."""
    for flow in diagram.data_flows:
        if flow.crosses_boundary and component_id in (flow.source, flow.destination):
            return True
    return False


def build_component_profile(diagram: ArchitectureDiagram, component_id: str) -> str:
    """Perfil textual do componente para o prompt (texto simples, não JSON)."""
    component = next(c for c in diagram.components if c.id == component_id)
    crosses = component_crosses_boundary(diagram, component_id)

    linhas = [
        f"Nome: {component.name}",
        f"Tipo (element_type): {component.element_type}",
        f"Serviço cloud: {component.aws_service or 'não especificado'}",
        f"Trust boundary: {component.trust_boundary}",
        f"Cruza trust boundary: {'sim' if crosses else 'não'}",
    ]
    return "\n".join(linhas)


def render_kg_context(kg_result: KGQueryResult) -> str:
    """Renderiza as categorias/ameaças/mitigações canônicas do KG como texto
    legível, truncado a 6000 caracteres.

    Truncamento determinístico: reservamos espaço para o marcador de corte e
    cortamos no fim da última linha completa que couber (nunca no meio de uma
    linha). O resultado final tem SEMPRE no máximo 6000 caracteres.
    """
    _MARKER = "\n[... contexto truncado em 6000 caracteres ...]"
    if not kg_result.stride_results:
        return "Nenhuma ameaça canônica encontrada no Knowledge Graph."

    linhas: list[str] = []
    for stride in kg_result.stride_results:
        linhas.append(f"## {stride.letter} — {stride.category}")
        if stride.threats:
            linhas.append("Ameaças canônicas:")
            for threat in stride.threats:
                linhas.append(
                    f"- {threat.name} (severidade: {threat.severity}): "
                    f"{threat.description}"
                )
        if stride.mitigations:
            linhas.append("Mitigações canônicas:")
            for mitigation in stride.mitigations:
                linhas.append(
                    f"- {mitigation.name} ({mitigation.control_type}): "
                    f"{mitigation.description}"
                )
        linhas.append("")  # separador entre categorias

    texto = "\n".join(linhas).rstrip()

    if len(texto) <= _KG_CONTEXT_MAX_CHARS:
        return texto

    # Reserva espaço para o marcador; corta no fim da última linha completa.
    budget = _KG_CONTEXT_MAX_CHARS - len(_MARKER)
    recorte = texto[:budget]
    ultima_quebra = recorte.rfind("\n")
    if ultima_quebra > 0:
        recorte = recorte[:ultima_quebra]
    return recorte.rstrip() + _MARKER
