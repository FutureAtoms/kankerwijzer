from __future__ import annotations

from typing import Any

from app.connectors.firecrawl_client import FirecrawlClient


class IKNLWebConnector:
    ENTRYPOINTS = {
        "nkr": "https://iknl.nl/nkr",
        "cancer_types": "https://iknl.nl/kankersoorten",
        "news": "https://iknl.nl/nieuws",
        "publications": "https://iknl.nl/onderzoek/publicaties",
    }

    def __init__(self, firecrawl: FirecrawlClient) -> None:
        self.firecrawl = firecrawl

    def scrape_page(self, url: str) -> Any:
        return self.firecrawl.scrape(url, formats=["markdown", "html"])

    def crawl_entrypoint(self, url: str = "https://iknl.nl/kankersoorten") -> Any:
        return self.firecrawl.crawl(url, limit=25, formats=["markdown"])

    def key_entrypoints(self) -> dict[str, Any]:
        return {name: self.scrape_page(url) for name, url in self.ENTRYPOINTS.items()}
