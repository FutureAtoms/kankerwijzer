from __future__ import annotations

from typing import Any

from app.config import Settings
from app.connectors.firecrawl_client import FirecrawlClient
from app.connectors.iknl import IKNLWebConnector
from app.connectors.kanker_nl import LocalKankerNLDataset
from app.connectors.kankeratlas import KankerAtlasClient
from app.connectors.nkr_cijfers import NKRCijfersClient
from app.connectors.publications import PublicationsConnector
from app.connectors.richtlijnendatabase import RichtlijnendatabaseConnector


class SourceVerifier:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.firecrawl = FirecrawlClient(settings)
        self.iknl = IKNLWebConnector(self.firecrawl)
        self.kanker_nl = LocalKankerNLDataset(settings)
        self.kankeratlas = KankerAtlasClient(settings)
        self.nkr = NKRCijfersClient(settings)
        self.publications = PublicationsConnector(settings, self.firecrawl)
        self.richtlijn = RichtlijnendatabaseConnector(self.firecrawl)

    def _result(self, name: str, checks: list[dict[str, Any]]) -> dict[str, Any]:
        passed = sum(1 for check in checks if check["status"] == "pass")
        return {
            "source": name,
            "passed": passed,
            "total": len(checks),
            "status": "pass" if passed == len(checks) else "fail",
            "checks": checks,
        }

    def verify_iknl(self) -> dict[str, Any]:
        pages = self.iknl.key_entrypoints()
        checks = []
        for name, payload in pages.items():
            metadata = payload.get("metadata", {})
            markdown = payload.get("markdown", "")
            checks.append(
                {
                    "check": f"iknl entrypoint {name}",
                    "status": "pass" if metadata.get("status_code") == 200 and len(markdown) > 200 else "fail",
                    "details": {
                        "url": payload.get("url"),
                        "title": metadata.get("title"),
                        "status_code": metadata.get("status_code"),
                        "markdown_length": len(markdown),
                    },
                }
            )
        return self._result("iknl.nl.md", checks)

    def verify_kanker_nl(self) -> dict[str, Any]:
        live = self.kanker_nl.live_sample_page()
        robots = self.kanker_nl.robots_txt()
        checks = [
            {
                "check": "bundled kanker.nl dataset present",
                "status": "pass" if len(self.kanker_nl.pages) >= 2000 else "fail",
                "details": {"page_count": len(self.kanker_nl.pages)},
            },
            {
                "check": "kanker.nl live sample page",
                "status": "pass" if live["status_code"] == 200 and len(str(live["excerpt"])) > 100 else "fail",
                "details": live,
            },
            {
                "check": "kanker.nl robots.txt",
                "status": "pass" if "User-agent" in robots or "user-agent" in robots.lower() else "fail",
                "details": {"excerpt": robots[:300]},
            },
        ]
        return self._result("kanker.nl.md", checks)

    def verify_kankeratlas(self) -> dict[str, Any]:
        filters = self.kankeratlas.filters()
        groups = self.kankeratlas.cancer_groups()
        postcodes = self.kankeratlas.postcodes(3)
        data = self.kankeratlas.cancer_data(11, 3, 3)
        postcode_rows = postcodes.get("res", []) if isinstance(postcodes, dict) else []
        data_rows = data.get("res", []) if isinstance(data, dict) else []
        has_103 = any(row.get("postcode") == 103 and "p50" in row for row in data_rows if isinstance(row, dict))
        checks = [
            {
                "check": "kankeratlas filters endpoint",
                "status": "pass" if {"indicator", "cancergrp", "sex", "pc"}.issubset(filters.keys()) else "fail",
                "details": {"keys": sorted(filters.keys())},
            },
            {
                "check": "kankeratlas cancer groups endpoint",
                "status": "pass" if isinstance(groups, list) and len(groups) > 0 else "fail",
                "details": {"count": len(groups), "first": groups[0] if groups else None},
            },
            {
                "check": "kankeratlas postcodes endpoint",
                "status": "pass" if len(postcode_rows) > 0 and "areacode" in postcode_rows[0] else "fail",
                "details": {"count": len(postcode_rows), "first": postcode_rows[0] if postcode_rows else None},
            },
            {
                "check": "kankeratlas cancer data endpoint",
                "status": "pass" if len(data_rows) > 0 and has_103 else "fail",
                "details": {
                    "count": len(data_rows),
                    "sample_103": next((row for row in data_rows if row.get("postcode") == 103), None),
                },
            },
        ]
        return self._result("kankeratlas.iknl.nl.md", checks)

    def verify_nkr(self) -> dict[str, Any]:
        code = "incidentie/verdeling-per-stadium"
        navigation = self.nkr.navigation_items()
        configuration = self.nkr.configuration(code)
        filter_groups = self.nkr.filter_groups(code)
        data = self.nkr.example_stage_distribution()
        checks = [
            {
                "check": "nkr navigation-items endpoint",
                "status": "pass" if "defaultNavigation" in navigation and "items" in navigation else "fail",
                "details": {
                    "defaultNavigation": navigation.get("defaultNavigation"),
                    "item_count": len(navigation.get("items", [])),
                },
            },
            {
                "check": "nkr configuration endpoint",
                "status": "pass" if configuration else "fail",
                "details": {"keys": sorted(configuration.keys()) if isinstance(configuration, dict) else type(configuration).__name__},
            },
            {
                "check": "nkr filter-groups endpoint",
                "status": "pass" if filter_groups else "fail",
                "details": {
                    "keys": sorted(filter_groups.keys()) if isinstance(filter_groups, dict) else type(filter_groups).__name__,
                },
            },
            {
                "check": "nkr data endpoint",
                "status": "pass" if data else "fail",
                "details": {"keys": sorted(data.keys()) if isinstance(data, dict) else type(data).__name__},
            },
        ]
        return self._result("nkr-cijfers.nl.md", checks)

    def verify_publications(self) -> dict[str, Any]:
        index_page = self.publications.scrape_publications_index()
        report_pages = self.publications.scrape_report_pages()
        checks = [
            {
                "check": "publications index page",
                "status": "pass" if index_page.get("metadata", {}).get("status_code") == 200 else "fail",
                "details": {
                    "url": index_page.get("url"),
                    "title": index_page.get("metadata", {}).get("title"),
                    "markdown_length": len(index_page.get("markdown", "")),
                },
            },
            {
                "check": "bundled local reports exist",
                "status": "pass" if len(self.publications.list_local_reports()) >= 3 else "fail",
                "details": {"count": len(self.publications.list_local_reports())},
            },
            {
                "check": "bundled scientific publications exist",
                "status": "pass" if len(self.publications.list_local_publications()) >= 5 else "fail",
                "details": {"count": len(self.publications.list_local_publications())},
            },
        ]
        for url, payload in report_pages.items():
            checks.append(
                {
                    "check": f"report page {url}",
                    "status": "pass" if payload.get("metadata", {}).get("status_code") == 200 else "fail",
                    "details": {
                        "title": payload.get("metadata", {}).get("title"),
                        "markdown_length": len(payload.get("markdown", "")),
                    },
                }
            )

        try:
            parsed = self.publications.parse_local_pdf(self.publications.list_local_reports()[0])
            checks.append(
                {
                    "check": "local report pdf parse",
                    "status": "pass" if parsed.get("text_length", 0) > 500 else "fail",
                    "details": {
                        "source": parsed.get("source"),
                        "text_length": parsed.get("text_length"),
                    },
                }
            )
        except Exception as exc:
            checks.append(
                {
                    "check": "local report pdf parse",
                    "status": "fail",
                    "details": {"error": str(exc)},
                }
            )
        return self._result("publicaties.md", checks)

    def verify_richtlijnendatabase(self) -> dict[str, Any]:
        payload = self.richtlijn.scrape_guideline()
        checks = [
            {
                "check": "richtlijn example guideline page",
                "status": "pass"
                if payload.get("metadata", {}).get("status_code") == 200 and len(payload.get("markdown", "")) > 200
                else "fail",
                "details": {
                    "url": payload.get("url"),
                    "title": payload.get("metadata", {}).get("title"),
                    "markdown_length": len(payload.get("markdown", "")),
                },
            }
        ]
        return self._result("richtlijnendatabase.nl.md", checks)

    def verify_all(self) -> dict[str, Any]:
        results = [
            self.verify_iknl(),
            self.verify_kanker_nl(),
            self.verify_kankeratlas(),
            self.verify_nkr(),
            self.verify_publications(),
            self.verify_richtlijnendatabase(),
        ]
        passed = sum(1 for result in results if result["status"] == "pass")
        return {
            "passed_sources": passed,
            "total_sources": len(results),
            "status": "pass" if passed == len(results) else "fail",
            "results": results,
        }
