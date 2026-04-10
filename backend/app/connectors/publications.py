from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import Settings
from app.connectors.docling_parser import DoclingParser
from app.connectors.firecrawl_client import FirecrawlClient


class PublicationsConnector:
    PUBLICATIONS_INDEX = "https://iknl.nl/onderzoek/publicaties"
    REPORT_PAGES = [
        "https://iknl.nl/uitgezaaide-kanker-2025",
        "https://iknl.nl/eierstokkanker-nederland-2025",
    ]

    def __init__(self, settings: Settings, firecrawl: FirecrawlClient) -> None:
        self.settings = settings
        self.firecrawl = firecrawl
        self.docling = DoclingParser()

    def list_local_reports(self) -> list[str]:
        return sorted(str(path) for path in self.settings.reports_dir.glob("*.pdf"))

    def list_local_publications(self) -> list[str]:
        return sorted(str(path) for path in self.settings.scientific_publications_dir.glob("*.pdf"))

    def parse_local_pdf(self, path: str | Path) -> dict[str, Any]:
        return self.docling.parse(path)

    def scrape_publications_index(self) -> Any:
        return self.firecrawl.scrape(self.PUBLICATIONS_INDEX, formats=["markdown", "html"])

    def scrape_report_page(self, url: str) -> Any:
        return self.firecrawl.scrape(url, formats=["markdown", "html"])

    def scrape_report_pages(self) -> dict[str, Any]:
        return {url: self.scrape_report_page(url) for url in self.REPORT_PAGES}
