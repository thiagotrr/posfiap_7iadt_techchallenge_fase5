"""Testes unitários do loader Neo4j com driver simulado."""

from knowledge.crawler.crawler import CrawledDocument
from knowledge.ingestion.classifier import ClassificationResult
from knowledge.ingestion.loader import KGLoader


class FakeResult:
    def __init__(self, record=None):
        self.record = record

    def consume(self):
        return None

    def single(self):
        return self.record


class FakeSession:
    def __init__(self):
        self.calls = []
        self.results = iter(
            [
                FakeResult(),
                FakeResult({"linked": 1}),
                FakeResult({"linked": 1}),
                FakeResult(),
            ]
        )

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def run(self, query, **params):
        self.calls.append((query, params))
        return next(self.results)


class FakeDriver:
    def __init__(self):
        self.fake_session = FakeSession()

    def session(self):
        return self.fake_session


def test_load_s3_authentication_creates_source_and_links():
    doc = CrawledDocument(
        url="https://example.com/s3-auth",
        title="S3 authentication",
        text_content="Use strong authentication for S3.",
        source_name="Test",
        provider="aws",
        stride_hint=["S"],
        crawled_at="2026-07-20T12:00:00Z",
        content_hash="abc123",
    )
    classification = ClassificationResult(
        document_url=doc.url,
        stride_tags=["S"],
        element_types=["data_store"],
        relevant_services=["S3"],
        confidence="alta",
        classification_method="llm",
    )
    driver = FakeDriver()

    result = KGLoader().load(doc, classification, driver)

    assert result.source_node_id == "source-abc123"
    assert result.services_linked == 1
    assert result.categories_linked == 1
    queries = "\n".join(query for query, _ in driver.fake_session.calls)
    assert "MERGE (source:Source" in queries
    assert "COVERS_SERVICE" in queries
    assert "COVERS_CATEGORY" in queries
    assert "HAS_SPECIFIC_THREAT" in queries
    assert driver.fake_session.calls[1][1]["services"] == ["S3"]
    assert driver.fake_session.calls[2][1]["tags"] == ["S"]

