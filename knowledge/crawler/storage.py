"""
knowledge/crawler/storage.py

Persistência local dos documentos crawleados em JSON.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from knowledge.crawler.config import CRAWL_OUTPUT_DIR
from knowledge.crawler.crawler import CrawledDocument

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1"
MANIFEST_FILENAME = "crawl_manifest.json"


class CrawlStorage:
    """Armazena documentos crawleados em {output_dir}/{provider}/{content_hash}.json."""

    def __init__(self, output_dir: Path | str | None = None):
        self.output_dir = Path(output_dir or CRAWL_OUTPUT_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save(self, doc: CrawledDocument) -> Path:
        provider_dir = self.output_dir / doc.provider
        provider_dir.mkdir(parents=True, exist_ok=True)

        path = provider_dir / f"{doc.content_hash}.json"
        payload = {**asdict(doc), "schema_version": SCHEMA_VERSION}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load_all(self) -> list[CrawledDocument]:
        documents: list[CrawledDocument] = []
        for path in sorted(self.output_dir.rglob("*.json")):
            if path.name == MANIFEST_FILENAME:
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            data.pop("schema_version", None)
            documents.append(CrawledDocument(**data))
        return documents

    def exists(self, content_hash: str) -> bool:
        return any(self.output_dir.rglob(f"{content_hash}.json"))

    def get_stats(self) -> dict:
        docs = self.load_all()
        by_provider = Counter(d.provider for d in docs)
        by_stride_hint: Counter[str] = Counter()
        for doc in docs:
            for hint in doc.stride_hint:
                by_stride_hint[hint] += 1

        return {
            "total_documents": len(docs),
            "by_provider": dict(by_provider),
            "by_stride_hint": dict(by_stride_hint),
        }

    def save_manifest(
        self,
        targets_processed: list[str],
        documents: list[CrawledDocument],
    ) -> Path:
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "executed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "targets_processed": targets_processed,
            "total_documents": len(documents),
            "documents": [
                {
                    "url": doc.url,
                    "title": doc.title,
                    "provider": doc.provider,
                    "content_hash": doc.content_hash,
                    "source_name": doc.source_name,
                }
                for doc in documents
            ],
        }
        path = self.output_dir / MANIFEST_FILENAME
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Crawl manifest saved — path=%s documents=%d", path, len(documents))
        return path
