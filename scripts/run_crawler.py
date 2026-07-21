"""
scripts/run_crawler.py

Executa o crawler para todos os targets configurados e persiste o corpus localmente.

Uso:
    python scripts/run_crawler.py

Variáveis de ambiente opcionais:
    KG_CRAWL_OUTPUT_DIR       — diretório de saída (default: data/crawled/)
    KG_CRAWL_DELAY_S          — delay entre requests em segundos (default: 1.5)
    KG_CRAWL_REQUEST_TIMEOUT_S — timeout por request em segundos (default: 30)
"""

import logging
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

from knowledge.crawler.config import CRAWL_TARGETS
from knowledge.crawler.crawler import WebCrawler
from knowledge.crawler.storage import CrawlStorage

logger = logging.getLogger(__name__)


def main() -> int:
    crawler = WebCrawler()
    storage = CrawlStorage()
    saved_docs = []

    for target in CRAWL_TARGETS:
        documents = crawler.crawl(target)
        for doc in documents:
            if storage.exists(doc.content_hash):
                continue
            storage.save(doc)
            saved_docs.append(doc)

    all_docs = storage.load_all()
    storage.save_manifest(
        targets_processed=[t.name for t in CRAWL_TARGETS],
        documents=all_docs,
    )

    stats = storage.get_stats()
    total_chars = sum(len(d.text_content) for d in all_docs)

    print("\n=== Crawl Summary ===")
    print(f"Targets processed : {len(CRAWL_TARGETS)}")
    print(f"Documents saved   : {len(saved_docs)} (new this run)")
    print(f"Total in storage  : {stats['total_documents']}")
    print(f"By provider       : {stats['by_provider']}")
    print(f"By stride_hint    : {stats['by_stride_hint']}")
    print(f"Corpus size       : ~{total_chars:,} characters")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        logger.warning("Crawler interrupted by user.")
        raise SystemExit(130)
    except Exception as exc:
        logger.error("Crawler failed: %s", exc)
        raise SystemExit(1)
