"""
knowledge/crawler/config.py

Configuração de targets e parâmetros do crawler.
"""

import os
from dataclasses import dataclass
from pathlib import Path


USER_AGENT = "STRIDE-Analyzer-Academic-Crawler/1.0 (educational project)"

CRAWL_OUTPUT_DIR = Path(
    os.getenv("KG_CRAWL_OUTPUT_DIR", "data/crawled")
)

POLITENESS_DELAY_S = float(os.getenv("KG_CRAWL_DELAY_S", "1.5"))

REQUEST_TIMEOUT_S = float(os.getenv("KG_CRAWL_REQUEST_TIMEOUT_S", "30"))

SSL_VERIFY = os.getenv("KG_CRAWL_SSL_VERIFY", "true").lower() not in ("0", "false", "no")


@dataclass(frozen=True)
class CrawlTarget:
    url: str
    name: str
    provider: str
    max_depth: int
    allowed_path_prefix: str
    stride_hint: list[str]


CRAWL_TARGETS: list[CrawlTarget] = [
    CrawlTarget(
        url="https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/welcome.html",
        name="AWS Well-Architected Security Pillar",
        provider="aws",
        max_depth=2,
        allowed_path_prefix="/wellarchitected/latest/security-pillar/",
        stride_hint=["T", "I", "D", "E"],
    ),
    CrawlTarget(
        url="https://learn.microsoft.com/en-us/azure/security/fundamentals/",
        name="Azure Security Fundamentals",
        provider="azure",
        max_depth=2,
        allowed_path_prefix="/en-us/azure/security/fundamentals/",
        stride_hint=["S", "T", "I", "D"],
    ),
    CrawlTarget(
        url="https://learn.microsoft.com/en-us/azure/security/develop/threat-modeling-tool-threats",
        name="Microsoft STRIDE Threat Categories",
        provider="microsoft",
        max_depth=1,
        allowed_path_prefix="/en-us/azure/security/develop/",
        stride_hint=["S", "T", "R", "I", "D", "E"],
    ),
    CrawlTarget(
        url="https://cheatsheetseries.owasp.org/cheatsheets/Threat_Modeling_Cheat_Sheet.html",
        name="OWASP Threat Modeling Cheat Sheet",
        provider="owasp",
        max_depth=1,
        allowed_path_prefix="/cheatsheets/",
        stride_hint=["S", "T", "R", "I", "D", "E"],
    ),
]
