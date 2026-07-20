"""
knowledge/crawler/crawler.py

Web crawler com extração de texto limpo via BeautifulSoup4.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import certifi
import requests
from bs4 import BeautifulSoup

from knowledge.crawler.config import (
    CRAWL_TARGETS,
    CrawlTarget,
    POLITENESS_DELAY_S,
    REQUEST_TIMEOUT_S,
    SSL_VERIFY,
    USER_AGENT,
)

logger = logging.getLogger(__name__)

_REMOVE_TAGS = {"script", "style", "nav", "footer", "header", "noscript", "aside"}


@dataclass
class CrawledDocument:
    url: str
    title: str
    text_content: str
    source_name: str
    provider: str
    stride_hint: list[str]
    crawled_at: str
    content_hash: str


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def _extract_text(html: str) -> tuple[str, str]:
    """Extrai título e texto limpo do HTML."""
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup.find_all(_REMOVE_TAGS):
        tag.decompose()

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    parts: list[str] = []
    for element in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li"]):
        text = element.get_text(separator=" ", strip=True)
        if text:
            parts.append(text)

    return title, "\n\n".join(parts)


class WebCrawler:
    """Crawler simples com rate limiting, robots.txt e deduplicação por hash."""

    def __init__(
        self,
        politeness_delay_s: float = POLITENESS_DELAY_S,
        request_timeout_s: float = REQUEST_TIMEOUT_S,
        session: requests.Session | None = None,
    ):
        self.politeness_delay_s = politeness_delay_s
        self.request_timeout_s = request_timeout_s
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        if SSL_VERIFY:
            self.session.verify = certifi.where()
        else:
            import urllib3

            self.session.verify = False
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            logger.warning(
                "Crawler SSL verification disabled — set KG_CRAWL_SSL_VERIFY=true in production"
            )
        self._robots_cache: dict[str, RobotFileParser] = {}
        self._seen_hashes: set[str] = set()
        self._last_request_at: float = 0.0

    def crawl(self, target: CrawlTarget) -> list[CrawledDocument]:
        logger.info("Crawler started — target=%s url=%s", target.name, target.url)

        documents: list[CrawledDocument] = []
        visited: set[str] = set()
        queue: list[tuple[str, int]] = [(target.url, 0)]
        base_parsed = urlparse(target.url)

        while queue:
            url, depth = queue.pop(0)
            normalized = _normalize_url(url)

            if normalized in visited:
                continue
            visited.add(normalized)

            if depth > target.max_depth:
                continue

            if not self._url_allowed(url, target, base_parsed):
                continue

            if not self._can_fetch(url):
                logger.warning("Crawler blocked by robots.txt — url=%s", url)
                continue

            html = self._fetch(url)
            if html is None:
                continue

            title, text_content = _extract_text(html)
            if not text_content.strip():
                continue

            doc_hash = _content_hash(text_content)
            if doc_hash in self._seen_hashes:
                continue
            self._seen_hashes.add(doc_hash)

            documents.append(
                CrawledDocument(
                    url=url,
                    title=title or target.name,
                    text_content=text_content,
                    source_name=target.name,
                    provider=target.provider,
                    stride_hint=list(target.stride_hint),
                    crawled_at=_utc_now_iso(),
                    content_hash=doc_hash,
                )
            )

            if depth < target.max_depth:
                for link in self._extract_links(html, url):
                    if _normalize_url(link) not in visited:
                        queue.append((link, depth + 1))

        logger.info(
            "Crawler completed — target=%s documents=%d",
            target.name,
            len(documents),
        )
        return documents

    def crawl_all(self, targets: list[CrawlTarget] | None = None) -> list[CrawledDocument]:
        all_docs: list[CrawledDocument] = []
        for target in targets or CRAWL_TARGETS:
            all_docs.extend(self.crawl(target))
        return all_docs

    def _url_allowed(self, url: str, target: CrawlTarget, base_parsed) -> bool:
        parsed = urlparse(url)
        if parsed.netloc != base_parsed.netloc:
            return False
        if not parsed.path.startswith(target.allowed_path_prefix):
            return False
        if parsed.scheme not in ("http", "https"):
            return False
        return True

    def _get_robots(self, url: str) -> RobotFileParser:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"

        if origin not in self._robots_cache:
            rp = RobotFileParser()
            rp.set_url(urljoin(origin, "/robots.txt"))
            try:
                rp.read()
            except Exception:
                rp = RobotFileParser()
                rp.parse("User-agent: *\nDisallow:".splitlines())
            self._robots_cache[origin] = rp

        return self._robots_cache[origin]

    def _can_fetch(self, url: str) -> bool:
        return self._get_robots(url).can_fetch(USER_AGENT, url)

    def _wait_politeness(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.politeness_delay_s:
            time.sleep(self.politeness_delay_s - elapsed)

    def _fetch(self, url: str) -> str | None:
        self._wait_politeness()
        try:
            response = self.session.get(url, timeout=self.request_timeout_s)
            self._last_request_at = time.monotonic()
        except requests.Timeout:
            logger.warning("Crawler request failed — url=%s status_code=timeout", url)
            return None
        except requests.RequestException as exc:
            logger.warning(
                "Crawler request failed — url=%s status_code=%s",
                url,
                getattr(exc.response, "status_code", "error"),
            )
            return None

        if not response.ok:
            logger.warning(
                "Crawler request failed — url=%s status_code=%d",
                url,
                response.status_code,
            )
            return None

        return response.text

    def _extract_links(self, html: str, base_url: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        links: list[str] = []
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            if not href or href.startswith(("#", "mailto:", "javascript:")):
                continue
            absolute = urljoin(base_url, href)
            parsed = urlparse(absolute)
            if parsed.fragment:
                absolute = absolute.replace(f"#{parsed.fragment}", "")
            links.append(absolute)
        return links
