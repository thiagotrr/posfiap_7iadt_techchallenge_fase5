"""
tests/test_crawler.py

Testes unitários do WebCrawler com mock HTTP (sem chamadas reais à internet).
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from knowledge.crawler.config import CrawlTarget
from knowledge.crawler.crawler import WebCrawler, _content_hash, _extract_text


SAMPLE_HTML = """
<html>
<head><title>Security Best Practices</title></head>
<body>
<nav><a href="/nav">Skip</a></nav>
<header>Site Header</header>
<main>
  <h1>Authentication Controls</h1>
  <p>Protect user identity and prevent spoofing attacks.</p>
  <ul><li>Use MFA for all accounts</li></ul>
  <a href="/wellarchitected/latest/security-pillar/encryption.html">Encryption</a>
</main>
<footer>Copyright 2024</footer>
<script>track();</script>
</body>
</html>
"""

LINK_PAGE_HTML = """
<html><head><title>Encryption</title></head>
<body>
<h2>Data Encryption</h2>
<p>Encrypt data at rest and in transit to prevent information disclosure.</p>
</body></html>
"""


@pytest.fixture
def target() -> CrawlTarget:
    return CrawlTarget(
        url="https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/",
        name="AWS Security Test",
        provider="aws",
        max_depth=1,
        allowed_path_prefix="/wellarchitected/latest/security-pillar/",
        stride_hint=["T", "I"],
    )


class TestExtractText:
    def test_removes_boilerplate_and_preserves_content(self):
        title, text = _extract_text(SAMPLE_HTML)

        assert title == "Security Best Practices"
        assert "Authentication Controls" in text
        assert "spoofing attacks" in text
        assert "Use MFA" in text
        assert "Site Header" not in text
        assert "Copyright" not in text
        assert "track()" not in text


class TestWebCrawler:
    def test_crawl_extracts_clean_text(self, target):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.text = SAMPLE_HTML

        crawler = WebCrawler(politeness_delay_s=0)
        with patch.object(crawler.session, "get", return_value=mock_response):
            with patch.object(crawler, "_can_fetch", return_value=True):
                docs = crawler.crawl(target)

        assert len(docs) == 1
        assert "Authentication Controls" in docs[0].text_content
        assert docs[0].provider == "aws"
        assert docs[0].content_hash == _content_hash(docs[0].text_content)

    def test_robots_txt_blocked_url_is_skipped(self, target):
        crawler = WebCrawler(politeness_delay_s=0)
        with patch.object(crawler, "_can_fetch", return_value=False):
            docs = crawler.crawl(target)

        assert docs == []

    def test_timeout_logs_error_without_aborting_crawl(self, target):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.text = SAMPLE_HTML

        def side_effect(url, timeout):
            if "encryption" in url:
                raise requests.Timeout("timed out")
            return mock_response

        crawler = WebCrawler(politeness_delay_s=0)
        with patch.object(crawler.session, "get", side_effect=side_effect):
            with patch.object(crawler, "_can_fetch", return_value=True):
                docs = crawler.crawl(target)

        assert len(docs) >= 1

    def test_deduplication_by_content_hash(self, target):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.text = SAMPLE_HTML

        crawler = WebCrawler(politeness_delay_s=0)
        with patch.object(crawler.session, "get", return_value=mock_response):
            with patch.object(crawler, "_can_fetch", return_value=True):
                first = crawler.crawl(target)
                second = crawler.crawl(target)

        assert len(first) == 1
        assert len(second) == 0

    def test_respects_max_depth_and_path_prefix(self, target):
        main_response = MagicMock()
        main_response.ok = True
        main_response.text = SAMPLE_HTML

        link_response = MagicMock()
        link_response.ok = True
        link_response.text = LINK_PAGE_HTML

        def fetch_side_effect(url, timeout):
            if "encryption" in url:
                return link_response
            return main_response

        crawler = WebCrawler(politeness_delay_s=0)
        with patch.object(crawler.session, "get", side_effect=fetch_side_effect):
            with patch.object(crawler, "_can_fetch", return_value=True):
                docs = crawler.crawl(target)

        urls = {d.url for d in docs}
        assert any("security-pillar" in u for u in urls)
        assert any("encryption" in u for u in urls)

    def test_http_error_is_logged_and_skipped(self, target):
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 403

        crawler = WebCrawler(politeness_delay_s=0)
        with patch.object(crawler.session, "get", return_value=mock_response):
            with patch.object(crawler, "_can_fetch", return_value=True):
                docs = crawler.crawl(target)

        assert docs == []
