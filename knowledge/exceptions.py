"""
knowledge/exceptions.py

Exceções customizadas do módulo knowledge.
"""


class ElementTypeNotFoundError(ValueError):
    """Lançada quando element_type não existe no KG."""
    def __init__(self, element_type: str):
        self.element_type = element_type
        super().__init__(f"ElementType '{element_type}' not found in the Knowledge Graph.")


class IngestionError(RuntimeError):
    """Lançada quando o pipeline de ingestão falha de forma não recuperável."""


class CrawlerError(RuntimeError):
    """Lançada quando o crawler encontra um erro crítico."""
