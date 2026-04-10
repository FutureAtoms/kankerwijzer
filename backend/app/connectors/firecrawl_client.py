from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from app.config import Settings


class FirecrawlUnavailableError(RuntimeError):
    pass


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[override]
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        if tag in {"script", "style", "noscript"} and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag in {"p", "div", "section", "article", "li", "h1", "h2", "h3", "h4", "br"}:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:  # type: ignore[override]
        if self._skip_depth == 0:
            self._parts.append(data)

    def text(self) -> str:
        raw = unescape("".join(self._parts))
        cleaned = re.sub(r"\n{3,}", "\n\n", raw)
        return re.sub(r"[ \t]+", " ", cleaned).strip()


class FirecrawlClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _client(self) -> Any:
        if not self.settings.firecrawl_api_key:
            raise FirecrawlUnavailableError("FIRECRAWL_API_KEY is not configured.")
        try:
            from firecrawl import Firecrawl
        except ImportError as exc:
            raise FirecrawlUnavailableError(
                "firecrawl-py is not installed. Run `uv sync --extra firecrawl`."
            ) from exc
        return Firecrawl(api_key=self.settings.firecrawl_api_key)

    def _raw_scrape(self, url: str) -> dict[str, Any]:
        response = httpx.get(url, timeout=self.settings.request_timeout_seconds, follow_redirects=True)
        response.raise_for_status()
        html = response.text
        parser = _HTMLTextExtractor()
        parser.feed(html)
        markdown = parser.text()
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        title = unescape(title_match.group(1)).strip() if title_match else url
        return {
            "provider": "raw-http-fallback",
            "url": str(response.url),
            "metadata": {"title": title, "status_code": response.status_code},
            "markdown": markdown,
            "html": html,
        }

    def _extract_links(self, html: str, base_url: str) -> list[str]:
        hrefs = re.findall(r'href=["\\\'](.*?)["\\\']', html, flags=re.IGNORECASE)
        base = urlparse(base_url)
        links: list[str] = []
        for href in hrefs:
            absolute = urljoin(base_url, href)
            parsed = urlparse(absolute)
            if parsed.scheme not in {"http", "https"}:
                continue
            if parsed.netloc != base.netloc:
                continue
            normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
            if normalized and normalized not in links:
                links.append(normalized)
        return links

    def scrape(self, url: str, formats: list[str] | None = None) -> Any:
        try:
            client = self._client()
        except FirecrawlUnavailableError:
            return self._raw_scrape(url)
        return client.scrape(url, formats=formats or ["markdown"])

    def crawl(
        self,
        url: str,
        limit: int = 25,
        include_paths: list[str] | None = None,
        exclude_paths: list[str] | None = None,
        formats: list[str] | None = None,
    ) -> Any:
        try:
            client = self._client()
        except FirecrawlUnavailableError:
            first = self._raw_scrape(url)
            links = self._extract_links(first.get("html", ""), first["url"])
            if include_paths:
                links = [link for link in links if any(path in link for path in include_paths)]
            if exclude_paths:
                links = [link for link in links if not any(path in link for path in exclude_paths)]
            return {
                "provider": "raw-http-fallback",
                "start_url": first["url"],
                "documents": [first],
                "links": links[:limit],
                "limit": limit,
            }
        kwargs: dict[str, Any] = {
            "url": url,
            "limit": limit,
            "scrape_options": {"formats": formats or ["markdown"]},
        }
        if include_paths:
            kwargs["include_paths"] = include_paths
        if exclude_paths:
            kwargs["exclude_paths"] = exclude_paths
        return client.crawl(**kwargs)

    def map(self, url: str, search: str | None = None) -> Any:
        try:
            client = self._client()
        except FirecrawlUnavailableError:
            scraped = self._raw_scrape(url)
            links = self._extract_links(scraped.get("html", ""), scraped["url"])
            if search:
                lowered = search.lower()
                links = [link for link in links if lowered in link.lower()]
            return {"provider": "raw-http-fallback", "url": scraped["url"], "links": links}
        kwargs: dict[str, Any] = {"url": url}
        if search:
            kwargs["search"] = search
        return client.map(**kwargs)
