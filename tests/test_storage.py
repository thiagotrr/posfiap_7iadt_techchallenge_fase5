"""
tests/test_storage.py

Testes unitários do CrawlStorage.
"""

import json

import pytest

from knowledge.crawler.crawler import CrawledDocument
from knowledge.crawler.storage import CrawlStorage, SCHEMA_VERSION


@pytest.fixture
def sample_doc() -> CrawledDocument:
    return CrawledDocument(
        url="https://example.com/security",
        title="Security Guide",
        text_content="Protect authentication and encrypt sensitive data.",
        source_name="Test Source",
        provider="aws",
        stride_hint=["S", "I"],
        crawled_at="2026-07-14T12:00:00Z",
        content_hash="abc123hash",
    )


@pytest.fixture
def storage(tmp_path) -> CrawlStorage:
    return CrawlStorage(output_dir=tmp_path)


class TestCrawlStorage:
    def test_save_and_load_roundtrip(self, storage, sample_doc):
        path = storage.save(sample_doc)

        assert path.exists()
        loaded = storage.load_all()
        assert len(loaded) == 1
        assert loaded[0].url == sample_doc.url
        assert loaded[0].text_content == sample_doc.text_content
        assert loaded[0].content_hash == sample_doc.content_hash

    def test_save_includes_schema_version(self, storage, sample_doc):
        path = storage.save(sample_doc)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["schema_version"] == SCHEMA_VERSION

    def test_exists_detects_saved_document(self, storage, sample_doc):
        assert storage.exists(sample_doc.content_hash) is False
        storage.save(sample_doc)
        assert storage.exists(sample_doc.content_hash) is True

    def test_exists_prevents_duplicate_save(self, storage, sample_doc):
        storage.save(sample_doc)
        assert storage.exists(sample_doc.content_hash) is True

        docs_before = storage.load_all()
        if not storage.exists(sample_doc.content_hash):
            storage.save(sample_doc)
        docs_after = storage.load_all()

        assert len(docs_before) == len(docs_after) == 1

    def test_get_stats_counts_by_provider_and_hint(self, storage, sample_doc):
        storage.save(sample_doc)
        other = CrawledDocument(
            url="https://example.com/azure",
            title="Azure Security",
            text_content="Azure security fundamentals content.",
            source_name="Azure Source",
            provider="azure",
            stride_hint=["T", "D"],
            crawled_at="2026-07-14T12:00:00Z",
            content_hash="def456hash",
        )
        storage.save(other)

        stats = storage.get_stats()
        assert stats["total_documents"] == 2
        assert stats["by_provider"] == {"aws": 1, "azure": 1}
        assert stats["by_stride_hint"]["S"] == 1
        assert stats["by_stride_hint"]["T"] == 1

    def test_save_manifest(self, storage, sample_doc):
        storage.save(sample_doc)
        manifest_path = storage.save_manifest(
            targets_processed=["Test Target"],
            documents=[sample_doc],
        )

        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["total_documents"] == 1
        assert manifest["documents"][0]["content_hash"] == sample_doc.content_hash
