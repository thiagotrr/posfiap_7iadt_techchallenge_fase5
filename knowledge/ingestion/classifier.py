"""Classificação de documentos por categorias STRIDE e serviços de nuvem."""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, field_validator

from knowledge.crawler.crawler import CrawledDocument
from knowledge.graph_schema import (
    CANONICAL_CLOUD_SERVICE_NAMES,
    CLOUD_SERVICES,
    ELEMENT_TYPES,
    REFERENCE_ARCHITECTURE_SERVICES,
    STRIDE_LETTERS,
)
from knowledge.ingestion.classifier_prompt import CLASSIFICATION_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

MAX_CLASSIFICATION_TEXT_LENGTH = 4_000


class ClassificationResult(BaseModel):
    document_url: str
    stride_tags: list[str]
    element_types: list[str]
    relevant_services: list[str]
    confidence: Literal["alta", "média", "baixa"]
    classification_method: Literal["llm", "heuristic", "hint_only"]

    @field_validator("stride_tags")
    @classmethod
    def validate_stride_tags(cls, values: list[str]) -> list[str]:
        valid = set(STRIDE_LETTERS)
        return _unique(value.upper() for value in values if value.upper() in valid)

    @field_validator("element_types")
    @classmethod
    def validate_element_types(cls, values: list[str]) -> list[str]:
        valid = set(ELEMENT_TYPES)
        return _unique(value for value in values if value in valid)

    @field_validator("relevant_services")
    @classmethod
    def validate_services(cls, values: list[str]) -> list[str]:
        return _normalize_services(values)


class _LLMClassification(BaseModel):
    """Schema estruturado solicitado ao modelo via LangChain."""

    stride_tags: list[str] = Field(default_factory=list)
    element_types: list[str] = Field(default_factory=list)
    relevant_services: list[str] = Field(default_factory=list)


_STRIDE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "S": (
        "spoofing", "authentication", "authenticate", "identity", "credential",
        "impersonation", "mfa", "multi-factor",
    ),
    "T": (
        "tampering", "integrity", "unauthorized modification", "injection",
        "malicious modification", "checksum", "signature validation",
    ),
    "R": (
        "repudiation", "non-repudiation", "audit log", "audit trail",
        "accountability", "traceability",
    ),
    "I": (
        "information disclosure", "confidential", "confidentiality", "encryption",
        "encrypt", "sensitive data", "data exposure", "data leak", "privacy",
    ),
    "D": (
        "denial of service", "dos", "ddos", "availability", "rate limit",
        "rate-limit", "throttle", "resource exhaustion",
    ),
    "E": (
        "elevation of privilege", "privilege escalation", "least privilege",
        "authorization", "iam", "access control", "permission",
    ),
}

_ELEMENT_TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "process": (
        "service", "application", "compute", "function", "api", "workload",
        "container", "instance",
    ),
    "data_store": (
        "database", "storage", "bucket", "cache", "repository", "data store",
        "datastore", "table",
    ),
    "data_flow": (
        "data flow", "in transit", "traffic", "network connection", "request",
        "message", "communication",
    ),
    "external_entity": (
        "external entity", "third party", "third-party", "end user", "customer",
        "actor", "client",
    ),
}


class STRIDEClassifier:
    """Classifica via LLM e aplica fallbacks locais quando necessário."""

    def __init__(
        self,
        llm: BaseChatModel | Any | None = None,
        provider: str | None = None,
    ) -> None:
        self.provider = (
            provider
            or os.getenv("KG_CLASSIFIER_LLM_PROVIDER")
            or os.getenv("EXTRACTION_LLM_PROVIDER")
            or "openai"
        ).strip().lower()
        self._llm = llm
        self._structured_llm = None

    def _get_structured_llm(self):
        if self._structured_llm is None:
            llm = self._llm or _create_llm(self.provider)
            self._structured_llm = llm.with_structured_output(_LLMClassification)
        return self._structured_llm

    def classify(self, doc: CrawledDocument) -> ClassificationResult:
        try:
            llm_result = self._classify_with_llm(doc)
            if llm_result.stride_tags:
                return ClassificationResult(
                    document_url=doc.url,
                    stride_tags=llm_result.stride_tags,
                    element_types=llm_result.element_types,
                    relevant_services=llm_result.relevant_services,
                    confidence="alta",
                    classification_method="llm",
                )
            logger.warning("LLM classification returned no STRIDE tags — url=%s", doc.url)
        except Exception as exc:
            logger.warning(
                "LLM classification failed — url=%s provider=%s error=%s",
                doc.url,
                self.provider,
                type(exc).__name__,
            )

        heuristic = self._classify_heuristically(doc)
        if heuristic.stride_tags:
            return heuristic

        return ClassificationResult(
            document_url=doc.url,
            stride_tags=doc.stride_hint,
            element_types=[],
            relevant_services=_find_services(doc.text_content),
            confidence="baixa",
            classification_method="hint_only",
        )

    def _classify_with_llm(self, doc: CrawledDocument) -> _LLMClassification:
        structured_llm = self._get_structured_llm()
        text = doc.text_content[:MAX_CLASSIFICATION_TEXT_LENGTH]
        response = structured_llm.invoke(
            [
                SystemMessage(content=CLASSIFICATION_SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        f"URL: {doc.url}\n"
                        f"Título: {doc.title}\n"
                        f"Provider: {doc.provider}\n"
                        f"STRIDE hints: {doc.stride_hint}\n\n"
                        f"Conteúdo:\n{text}"
                    )
                ),
            ]
        )
        if isinstance(response, _LLMClassification):
            return response
        return _LLMClassification.model_validate(response)

    def _classify_heuristically(self, doc: CrawledDocument) -> ClassificationResult:
        text = f"{doc.title}\n{doc.text_content}".lower()
        services = _find_services(text)
        tags = [
            tag
            for tag, keywords in _STRIDE_KEYWORDS.items()
            if any(_contains_keyword(text, keyword) for keyword in keywords)
        ]
        element_types = [
            element_type
            for element_type, keywords in _ELEMENT_TYPE_KEYWORDS.items()
            if any(_contains_keyword(text, keyword) for keyword in keywords)
        ]
        service_element_types = {
            service["name"]: service["element_type"]
            for service in REFERENCE_ARCHITECTURE_SERVICES
        }
        element_types.extend(
            service_element_types[service]
            for service in services
            if service in service_element_types
        )
        return ClassificationResult(
            document_url=doc.url,
            stride_tags=tags,
            element_types=_unique(element_types),
            relevant_services=services,
            confidence="média",
            classification_method="heuristic",
        )


def _create_llm(provider: str) -> BaseChatModel:
    """Cria o chat model selecionado sem expor detalhes ao classificador."""
    temperature = 0

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is required for provider 'openai'.")
        return ChatOpenAI(
            model=os.getenv("KG_CLASSIFIER_OPENAI_MODEL", "gpt-4o-mini"),
            temperature=temperature,
        )

    if provider in {"gemini", "google", "google_genai"}:
        from langchain_google_genai import ChatGoogleGenerativeAI

        if not (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")):
            raise RuntimeError(
                "GOOGLE_API_KEY or GEMINI_API_KEY is required for provider 'gemini'."
            )
        return ChatGoogleGenerativeAI(
            model=os.getenv("KG_CLASSIFIER_GEMINI_MODEL", "gemini-2.5-flash"),
            temperature=temperature,
            api_key=os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"),
        )

    raise ValueError(
        "Unsupported KG classifier provider. Use 'openai' or 'gemini'."
    )


def _contains_keyword(text: str, keyword: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", text) is not None


def _find_services(text: str) -> list[str]:
    lowered = text.lower()
    aliases = sorted(CLOUD_SERVICES.items(), key=lambda item: len(item[0]), reverse=True)
    matches = [
        canonical
        for alias, canonical in aliases
        if _contains_keyword(lowered, alias.lower())
    ]
    return _normalize_services(matches)


def _normalize_services(values: list[str]) -> list[str]:
    aliases = {alias.lower(): canonical for alias, canonical in CLOUD_SERVICES.items()}
    canonical_lookup = {
        canonical.lower(): canonical for canonical in CANONICAL_CLOUD_SERVICE_NAMES
    }
    normalized: list[str] = []
    for value in values:
        cleaned = value.strip()
        canonical = aliases.get(cleaned.lower()) or canonical_lookup.get(cleaned.lower())
        if canonical:
            normalized.append(canonical)
    return _unique(normalized)


def _unique(values) -> list[str]:
    return list(dict.fromkeys(values))

