"""
knowledge.crawler — Web crawler de fontes de conhecimento STRIDE.

Coleta documentação pública (AWS, Azure, Microsoft, OWASP) para enriquecimento do KG.
"""

from knowledge.crawler.config import CRAWL_TARGETS, CrawlTarget
from knowledge.crawler.crawler import CrawledDocument, WebCrawler
from knowledge.crawler.storage import CrawlStorage

__all__ = [
    "CRAWL_TARGETS",
    "CrawlTarget",
    "CrawledDocument",
    "WebCrawler",
    "CrawlStorage",
]
