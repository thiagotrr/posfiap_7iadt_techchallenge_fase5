"""Templates de prompt para a análise e o refinamento STRIDE (Épico 2).

Contém apenas strings e um helper de schema — sem chamada de LLM. O
`LLMAnalysisClient` (US-2.3) consome estas constantes.

Racional (structured output): o schema exposto ao LLM é o de
`list[STRIDEThreatEntry]` (não o `ComponentAnalysis` completo), reduzindo o
tamanho do prompt. Ver CLAUDE.md, "Prompt de raciocínio STRIDE".
"""
from __future__ import annotations

from pydantic import TypeAdapter

from orchestration.models import STRIDEThreatEntry

# ---------------------------------------------------------------------------
# Análise STRIDE
# ---------------------------------------------------------------------------

STRIDE_ANALYSIS_SYSTEM_PROMPT = """\
Você é um especialista em modelagem de ameaças pela metodologia STRIDE da \
Microsoft, aplicada a arquiteturas de software em nuvem (AWS/Azure/GCP).

Você receberá:
1. O PERFIL de um componente específico de um diagrama de arquitetura (nome, \
element_type, serviço cloud, trust boundary e se ele cruza fronteiras de \
confiança).
2. As AMEAÇAS CANÔNICAS do Knowledge Graph STRIDE para esse tipo de componente, \
como material de contexto/referência.

Sua tarefa:
- Raciocine sobre quais categorias STRIDE realmente se aplicam a ESTE componente \
NESTE diagrama específico. NÃO repita a taxonomia genérica nem liste categorias \
que não fazem sentido para o componente em questão.
- Use as ameaças canônicas do KG como apoio, mas contextualize: descreva a \
ameaça em função do papel real do componente no diagrama.
- Para cada ameaça aplicável, forneça: nome objetivo, descrição contextualizada, \
severidade e mitigações concretas.
- Priorize ameaças de MAIOR severidade para componentes que CRUZAM trust \
boundaries (superfície de ataque exposta).

Campo `category` — use EXCLUSIVAMENTE uma das 6 letras STRIDE:
- S = Spoofing (falsificação de identidade)
- T = Tampering (adulteração)
- R = Repudiation (repúdio)
- I = Information Disclosure (divulgação de informação)
- D = Denial of Service (negação de serviço)
- E = Elevation of Privilege (elevação de privilégio)

Campo `severity`: use exclusivamente "critical", "high", "medium" ou "low".
Campo `source`: use "llm_only" (análise gerada por você a partir do contexto).

Retorne SOMENTE JSON válido conforme o schema fornecido (uma lista de ameaças). \
Não inclua texto fora do JSON, comentários ou markdown.\
"""

STRIDE_ANALYSIS_USER_TEMPLATE = """\
PERFIL DO COMPONENTE:
{component_profile}

AMEAÇAS CANÔNICAS DO KNOWLEDGE GRAPH (contexto de referência):
{kg_context}

SCHEMA JSON DE SAÍDA (retorne uma lista conforme este schema):
{json_schema}\
"""

# ---------------------------------------------------------------------------
# Refinamento (HITL)
# ---------------------------------------------------------------------------

REFINEMENT_SYSTEM_PROMPT = """\
Você é um especialista em modelagem de ameaças STRIDE. Você receberá uma ANÁLISE \
STRIDE já existente de um componente e um FEEDBACK textual de um revisor humano.

Sua tarefa é ATUALIZAR a análise conforme o feedback: adicionar, remover, \
reclassificar ou detalhar ameaças conforme solicitado, mantendo coerência com a \
metodologia STRIDE.

Regras:
- Preserve as ameaças que continuam válidas; só altere o que o feedback pede.
- Mantenha exatamente o MESMO schema de saída (lista de ameaças STRIDE).
- Campo `category`: exclusivamente uma das 6 letras S/T/R/I/D/E.
- Campo `severity`: "critical", "high", "medium" ou "low".
- Campo `source`: "llm_only".

Retorne SOMENTE JSON válido conforme o schema fornecido. Sem texto fora do JSON.\
"""

REFINEMENT_USER_TEMPLATE = """\
ANÁLISE ATUAL:
{current_analysis}

FEEDBACK DO REVISOR:
{user_feedback}

SCHEMA JSON DE SAÍDA (retorne uma lista conforme este schema):
{json_schema}\
"""


# ---------------------------------------------------------------------------
# Schema de saída
# ---------------------------------------------------------------------------

# TypeAdapter do topo do módulo evita reconstrução a cada chamada.
_STRIDE_ENTRIES_ADAPTER = TypeAdapter(list[STRIDEThreatEntry])


def stride_entries_json_schema() -> dict:
    """JSON Schema de `list[STRIDEThreatEntry]` para injetar no prompt.

    Nota: `category_name` aparece no schema exposto ao LLM. Não vale a pena
    duplicar o modelo só para omiti-lo — ele é sobrescrito pelo validator de
    STRIDEThreatEntry após o parse de qualquer forma (não é fonte de verdade).
    """
    return _STRIDE_ENTRIES_ADAPTER.json_schema()
