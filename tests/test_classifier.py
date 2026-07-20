"""Testes do classificador STRIDE em suas três camadas."""

from knowledge.crawler.crawler import CrawledDocument
from knowledge.ingestion.classifier import STRIDEClassifier


def _doc(text: str, hints: list[str] | None = None) -> CrawledDocument:
    return CrawledDocument(
        url="https://example.com/security",
        title="Security guidance",
        text_content=text,
        source_name="Test",
        provider="aws",
        stride_hint=hints or [],
        crawled_at="2026-07-20T12:00:00Z",
        content_hash="hash",
    )


class FakeLLM:
    def __init__(self, response):
        self.response = response
        self.messages = None

    def with_structured_output(self, _schema):
        return self

    def invoke(self, messages):
        self.messages = messages
        return self.response


class UnavailableLLM:
    def with_structured_output(self, _schema):
        raise RuntimeError("provider unavailable")


def test_llm_classification_normalizes_service_name():
    llm = FakeLLM(
        {
            "stride_tags": ["S", "I"],
            "element_types": ["data_store"],
            "relevant_services": ["Amazon S3"],
        }
    )

    result = STRIDEClassifier(llm=llm).classify(_doc("S3 authentication guidance"))

    assert result.classification_method == "llm"
    assert result.confidence == "alta"
    assert result.stride_tags == ["S", "I"]
    assert result.relevant_services == ["S3"]


def test_llm_receives_only_first_4000_content_characters():
    llm = FakeLLM(
        {
            "stride_tags": ["T"],
            "element_types": [],
            "relevant_services": [],
        }
    )
    classifier = STRIDEClassifier(llm=llm)

    classifier.classify(_doc("a" * 4_000 + "SECRET_TAIL"))

    human_prompt = llm.messages[1].content
    assert "a" * 4_000 in human_prompt
    assert "SECRET_TAIL" not in human_prompt


def test_unavailable_llm_falls_back_to_heuristic_for_s3():
    result = STRIDEClassifier(llm=UnavailableLLM()).classify(
        _doc("Amazon S3 authentication and encryption protect sensitive data.")
    )

    assert result.classification_method == "heuristic"
    assert result.confidence == "média"
    assert result.stride_tags == ["S", "I"]
    assert result.relevant_services == ["S3"]
    assert "data_store" in result.element_types


def test_generic_stride_document_gets_all_six_tags():
    result = STRIDEClassifier(llm=UnavailableLLM()).classify(
        _doc(
            "Spoofing, Tampering, Repudiation, Information Disclosure, "
            "Denial of Service and Elevation of Privilege."
        )
    )

    assert result.stride_tags == ["S", "T", "R", "I", "D", "E"]


def test_hint_only_is_final_fallback():
    result = STRIDEClassifier(llm=UnavailableLLM()).classify(
        _doc("Content without security classification terms.", hints=["T", "D"])
    )

    assert result.classification_method == "hint_only"
    assert result.confidence == "baixa"
    assert result.stride_tags == ["T", "D"]

