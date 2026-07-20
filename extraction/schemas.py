"""Contrato de dados: modelos Pydantic de um diagrama de arquitetura extraído.

Compartilhado por todos os módulos do pipeline (extração, KG, LangGraph, ...)
para que cada um possa mocar a saída do extrator sem depender da implementação
real. Ver `extraction/fixtures.py` para um exemplo instanciado e
`extraction/README.md` para como usá-los.
"""

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, model_validator

ElementType = Literal["process", "data_store", "data_flow", "external_entity"]

# extra="forbid" em todo elemento do diagrama: além de pegar erros de
# digitação na extração, é o que faz um ElementPatch de "update" com nome de
# campo errado falhar alto (PatchValidationError) em vez de silenciosamente
# não fazer nada -- ver apply_patch em extraction/service.py.
_STRICT = ConfigDict(extra="forbid")


class DiagramMetadata(BaseModel):
    model_config = _STRICT

    cloud_provider: str
    region: Optional[str] = None
    # Texto livre, nao Literal["alta","média","baixa"]: o JSON de referencia
    # do time usa frases explicativas (ex.: "média - contém ambiguidades a
    # validar via HITL"), nao so o rotulo puro. predict.py ainda produz um
    # dos tres rotulos base; HITL pode enriquecer com a justificativa.
    extraction_confidence: str


class TrustBoundary(BaseModel):
    model_config = _STRICT

    id: str
    name: str
    type: str
    parent: Optional[str] = None
    # Preenchidos pelo extrator automático (ex.: vision-detector); ausentes
    # em diagramas montados manualmente (fixtures, HITL "add"). confidence é
    # a confiança de detecção do marcador de canto da boundary; note sinaliza
    # quando o retângulo não pôde ser rastreado com precisão ou o rótulo não
    # foi lido via OCR -- prioriza o que revisar no HITL.
    confidence: Optional[float] = None
    note: Optional[str] = None


class Component(BaseModel):
    model_config = _STRICT

    id: str
    name: str
    aws_service: Optional[str] = None
    element_type: ElementType
    category: Optional[str] = None
    trust_boundary: str
    instance_count: Optional[int] = None
    confidence: Optional[float] = None
    note: Optional[str] = None


class DataFlow(BaseModel):
    model_config = _STRICT

    id: str
    source: str
    destination: str
    protocol: str
    crosses_boundary: bool
    confidence: Optional[float] = None
    note: Optional[str] = None


class ArchitectureDiagram(BaseModel):
    model_config = _STRICT

    diagram_metadata: DiagramMetadata
    trust_boundaries: list[TrustBoundary]
    components: list[Component]
    data_flows: list[DataFlow]

    @model_validator(mode="after")
    def _check_referential_integrity(self) -> "ArchitectureDiagram":
        boundary_ids = {tb.id for tb in self.trust_boundaries}
        component_ids = {c.id for c in self.components}

        for tb in self.trust_boundaries:
            if tb.parent is not None and tb.parent not in boundary_ids:
                raise ValueError(
                    f"TrustBoundary '{tb.id}' referencia parent '{tb.parent}' "
                    "que não existe em trust_boundaries"
                )

        for c in self.components:
            if c.trust_boundary not in boundary_ids:
                raise ValueError(
                    f"Component '{c.id}' referencia trust_boundary "
                    f"'{c.trust_boundary}' que não existe em trust_boundaries"
                )

        for f in self.data_flows:
            if f.source not in component_ids:
                raise ValueError(
                    f"DataFlow '{f.id}' referencia source '{f.source}' "
                    "que não existe em components"
                )
            if f.destination not in component_ids:
                raise ValueError(
                    f"DataFlow '{f.id}' referencia destination '{f.destination}' "
                    "que não existe em components"
                )

        return self


PatchElementType = Literal["component", "data_flow", "trust_boundary", "metadata"]
PatchOp = Literal["update", "add", "remove"]


class ElementPatch(BaseModel):
    """Uma correção pontual num elemento do diagrama.

    Três operações (não só "update" campo-a-campo): com um extrator baseado
    em detecção de objetos (vision-detector), o erro mais comum não é "campo
    errado" e sim "faltou detectar" (falso negativo) ou "detectou algo que
    não existe" (falso positivo, ex.: boundary fantasma traçada por Canny).
    "update" sozinho não consegue expressar essas correções sem reenviar o
    diagrama inteiro -- o que contradiz o objetivo de patch "cirúrgico".

    - update: exige `element_id` e `field`; `value` é o novo valor do campo.
      Não se aplica a `metadata` (não tem lista, nem `element_id`).
    - add: exige `value` com o elemento completo (dict serializável pelo
      modelo correspondente, incluindo `id` exceto para `metadata`).
    - remove: exige `element_id`; remove o elemento da lista correspondente.
    """

    model_config = _STRICT

    op: PatchOp = "update"
    element_type: PatchElementType
    element_id: Optional[str] = None
    field: Optional[str] = None
    value: Any = None

    @model_validator(mode="after")
    def _check_shape(self) -> "ElementPatch":
        if self.element_type == "metadata" and self.op != "update":
            raise ValueError("patches de 'metadata' só suportam op='update' (não há lista para add/remove)")

        if self.op == "update":
            if self.element_type != "metadata" and not self.element_id:
                raise ValueError("patch 'update' exige 'element_id'")
            if not self.field:
                raise ValueError("patch 'update' exige 'field'")
        elif self.op == "remove":
            if not self.element_id:
                raise ValueError("patch 'remove' exige 'element_id'")
        elif self.op == "add":
            if not isinstance(self.value, dict):
                raise ValueError("patch 'add' exige 'value' com o elemento completo (dict)")
            if "id" not in self.value:
                raise ValueError("patch 'add' exige 'id' dentro de 'value'")

        return self


class DiagramPatch(BaseModel):
    model_config = _STRICT

    patches: list[ElementPatch]
