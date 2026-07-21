"""
Avaliação nível-diagrama: roda o pipeline completo (detect_architecture) numa
imagem e compara o ArchitectureDiagram resultante com um gabarito anotado à
mão, usando extraction.eval.compare_diagrams.

Complementar a eval_against_ground_truth.py (que mede acerto do DETECTOR via
IoU de bounding boxes). Aqui a pergunta é se o ArchitectureDiagram FINAL --
depois do pós-processamento de containment/OCR/matching de seta -- está
estruturalmente correto. Um detector com boa precisão/recall de caixas ainda
pode montar um data flow errado ou aninhar uma trust boundary no lugar
errado; só a comparação nível-diagrama pega esse tipo de erro.

PRECISA de pelo menos um `expected_*.json` por imagem: um ArchitectureDiagram
válido anotado à mão (mesmo formato de extraction/fixtures.py::example_diagram).
Nenhum existe ainda no repositório -- isso é trabalho de anotação, não de
código. Para criar um gabarito:
    1. python predict.py <imagem>          # gera <imagem>_architecture.json
    2. copie e corrija manualmente esse JSON até refletir o diagrama de
       verdade (ids podem ser quaisquer strings -- a comparação é por
       distribuição de element_type/category, não por id).

Uso:
    python eval_diagram_level.py <imagem> <expected.json>
"""

import json
import sys
from pathlib import Path

from predict import detect_architecture  # reaproveita o fixup de sys.path do próprio predict.py

from extraction.eval import compare_diagrams
from extraction.schemas import ArchitectureDiagram


def main() -> None:
    if len(sys.argv) < 3:
        print("Uso: python eval_diagram_level.py <imagem> <expected.json>")
        sys.exit(1)

    image_path, expected_path = sys.argv[1], sys.argv[2]

    predicted = detect_architecture(image_path)
    expected = ArchitectureDiagram.model_validate(json.loads(Path(expected_path).read_text(encoding="utf-8")))

    metrics = compare_diagrams(predicted, expected)
    print(json.dumps(metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
