from __future__ import annotations

from typing import Any

from app.connectors.firecrawl_client import FirecrawlClient


class RichtlijnendatabaseConnector:
    EXAMPLE_GUIDELINE = (
        "https://richtlijnendatabase.nl/richtlijn/prostaatcarcinoom/"
        "prostaatcarcinoom_-_korte_beschrijving.html"
    )

    def __init__(self, firecrawl: FirecrawlClient) -> None:
        self.firecrawl = firecrawl

    def scrape_guideline(self, url: str | None = None) -> Any:
        return self.firecrawl.scrape(url or self.EXAMPLE_GUIDELINE, formats=["markdown", "html"])
