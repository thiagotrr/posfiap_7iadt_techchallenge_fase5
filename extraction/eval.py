"""Comparação nível-diagrama: quão perto um ArchitectureDiagram extraído está
de um ArchitectureDiagram de referência (ground truth anotado à mão).

Complementar a models/vision-detector/eval_against_ground_truth.py (que mede
IoU de bounding boxes -- acerto do detector). Aqui a pergunta é outra: o
ArchitectureDiagram FINAL, depois do pós-processamento (containment de trust
boundary, matching seta->componente, OCR), está estruturalmente correto? Um
detector pode acertar todas as caixas e o pipeline ainda assim montar um data
flow errado ou aninhar uma boundary no lugar errado -- e é exatamente essa a
métrica pedida para a validação do MVP (taxa de componentes/flows corretos no
diagrama final, não taxa de caixas corretas).

O contrato ArchitectureDiagram é semântico, não geométrico (sem bounding
boxes) -- não há como casar 1:1 "este Component predito é aquele esperado"
com certeza, já que o extrator gera ids sintéticos (`c_database_1`) sem
relação com os ids do gabarito. Por isso a comparação é por DISTRIBUIÇÃO
(quantos elementos de cada `element_type`/`category`), não por id.
"""

from collections import Counter
from typing import Any

from extraction.schemas import ArchitectureDiagram


def _multiset_f1(predicted: Counter, expected: Counter) -> float:
    """F1 sobre a interseção de multiconjuntos (contagens por chave).

    1.0 quando as distribuições batem exatamente (mesmas chaves, mesmas
    contagens); 0.0 quando não há nenhuma sobreposição.
    """
    overlap = sum((predicted & expected).values())
    if overlap == 0:
        return 1.0 if not predicted and not expected else 0.0
    precision = overlap / sum(predicted.values())
    recall = overlap / sum(expected.values())
    return 2 * precision * recall / (precision + recall)


def compare_diagrams(predicted: ArchitectureDiagram, expected: ArchitectureDiagram) -> dict[str, Any]:
    """Métricas de similaridade estrutural entre dois ArchitectureDiagram.

    Inclui também quanto do `predicted` está sinalizado (`note` preenchido ou
    confiança baixa) -- serve como proxy de "quanto trabalho de HITL esse
    diagrama provavelmente exige", independente de haver gabarito ou não.
    """
    pred_types = Counter(c.element_type for c in predicted.components)
    exp_types = Counter(c.element_type for c in expected.components)

    pred_categories = Counter(c.category for c in predicted.components if c.category)
    exp_categories = Counter(c.category for c in expected.components if c.category)

    return {
        "component_count": {"predicted": len(predicted.components), "expected": len(expected.components)},
        "data_flow_count": {"predicted": len(predicted.data_flows), "expected": len(expected.data_flows)},
        "trust_boundary_count": {
            "predicted": len(predicted.trust_boundaries), "expected": len(expected.trust_boundaries),
        },
        "element_type_distribution_f1": _multiset_f1(pred_types, exp_types),
        "category_distribution_f1": _multiset_f1(pred_categories, exp_categories),
        "components_low_confidence": sum(
            1 for c in predicted.components if c.confidence is not None and c.confidence < 0.5
        ),
        "components_flagged_for_review": sum(1 for c in predicted.components if c.note),
        "flows_flagged_for_review": sum(1 for f in predicted.data_flows if f.note),
        "boundaries_flagged_for_review": sum(1 for b in predicted.trust_boundaries if b.note),
    }
