"""Exceções do pipeline de extração e do HITL de correção."""


class ExtractionError(Exception):
    """Base para erros do módulo extraction."""


class ExtractionFailedError(ExtractionError):
    """A extração (chamada ao vision-detector) falhou ou não produziu um
    ArchitectureDiagram válido."""


class PatchElementNotFoundError(ExtractionError):
    """Um ElementPatch referencia element_id que não existe no diagrama atual."""

    def __init__(self, element_type: str, element_id: str):
        self.element_type = element_type
        self.element_id = element_id
        super().__init__(f"{element_type} '{element_id}' não encontrado no diagrama")


class PatchValidationError(ExtractionError):
    """Aplicar o(s) patch(es) deixaria o ArchitectureDiagram em estado inválido
    (ex.: campo inexistente, referência quebrada após remove)."""
