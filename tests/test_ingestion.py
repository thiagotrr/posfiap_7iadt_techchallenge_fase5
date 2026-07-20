"""Testes do orquestrador condicional de ingestão."""

from knowledge.crawler.crawler import CrawledDocument
from knowledge.ingestion.classifier import ClassificationResult
from knowledge.ingestion import pipeline


def test_populated_kg_skips_ingestion(monkeypatch):
    monkeypatch.setattr(pipeline, "_kg_has_complete_seed", lambda _driver: True)
    monkeypatch.setattr(pipeline, "_kg_has_enrichment", lambda _driver: True)
    seed_called = False

    def fake_seed(_driver):
        nonlocal seed_called
        seed_called = True

    monkeypatch.setattr(pipeline, "run_seed", fake_seed)

    result = pipeline.run_ingestion(driver=object())

    assert result.status == "skipped"
    assert result.documents_processed == 0
    assert seed_called is False


def test_empty_kg_runs_seed_and_ingests_documents(monkeypatch, tmp_path):
    doc = CrawledDocument(
        url="https://example.com/s3",
        title="S3 security",
        text_content="Authentication and encryption.",
        source_name="Test",
        provider="aws",
        stride_hint=["S", "I"],
        crawled_at="2026-07-20T12:00:00Z",
        content_hash="hash",
    )
    (tmp_path / "crawl_manifest.json").write_text("{}", encoding="utf-8")

    class FakeStorage:
        output_dir = tmp_path

        def load_all(self):
            return [doc]

    class FakeClassifier:
        def classify(self, document):
            return ClassificationResult(
                document_url=document.url,
                stride_tags=["S", "I"],
                element_types=["data_store"],
                relevant_services=["S3"],
                confidence="alta",
                classification_method="llm",
            )

    loaded = []

    class FakeLoader:
        def load(self, document, classification, driver):
            loaded.append((document, classification, driver))

    seed_calls = []
    driver = object()
    monkeypatch.setattr(pipeline, "_kg_has_complete_seed", lambda _driver: False)
    monkeypatch.setattr(pipeline, "run_seed", lambda active_driver: seed_calls.append(active_driver))
    monkeypatch.setattr(pipeline, "CrawlStorage", FakeStorage)
    monkeypatch.setattr(pipeline, "STRIDEClassifier", FakeClassifier)
    monkeypatch.setattr(pipeline, "KGLoader", FakeLoader)

    result = pipeline.run_ingestion(driver=driver)

    assert result.status == "completed"
    assert result.documents_processed == 1
    assert result.documents_failed == 0
    assert seed_calls == [driver]
    assert len(loaded) == 1


def test_seed_complete_with_manifest_still_ingests(monkeypatch, tmp_path):
    doc = CrawledDocument(
        url="https://example.com/s3",
        title="S3 security",
        text_content="Authentication and encryption.",
        source_name="Test",
        provider="aws",
        stride_hint=["S", "I"],
        crawled_at="2026-07-20T12:00:00Z",
        content_hash="hash",
    )
    (tmp_path / "crawl_manifest.json").write_text("{}", encoding="utf-8")

    class FakeStorage:
        output_dir = tmp_path

        def load_all(self):
            return [doc]

    loaded = []

    class FakeLoader:
        def load(self, document, classification, driver):
            loaded.append(document)

    seed_calls = []
    monkeypatch.setattr(pipeline, "_kg_has_complete_seed", lambda _driver: True)
    monkeypatch.setattr(pipeline, "_kg_has_enrichment", lambda _driver: False)
    monkeypatch.setattr(pipeline, "run_seed", lambda active_driver: seed_calls.append(active_driver))
    monkeypatch.setattr(pipeline, "CrawlStorage", FakeStorage)
    monkeypatch.setattr(
        pipeline,
        "STRIDEClassifier",
        lambda: type("FakeClassifier", (), {"classify": lambda self, document: ClassificationResult(
            document_url=document.url,
            stride_tags=["S", "I"],
            element_types=["data_store"],
            relevant_services=["S3"],
            confidence="média",
            classification_method="heuristic",
        )})(),
    )
    monkeypatch.setattr(pipeline, "KGLoader", FakeLoader)

    result = pipeline.run_ingestion(driver=object())

    assert result.status == "completed"
    assert result.documents_processed == 1
    assert seed_calls == []
    assert len(loaded) == 1

