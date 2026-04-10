from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings


class NKRCijfersClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = "https://api.nkr-cijfers.iknl.nl/api"

    def _post(self, path: str, body: dict[str, Any]) -> Any:
        response = httpx.post(
            f"{self.base_url}/{path}?format=json",
            json=body,
            timeout=self.settings.request_timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def navigation_items(self, language: str = "nl-NL") -> Any:
        return self._post("navigation-items", {"language": language})

    def configuration(self, code: str, language: str = "nl-NL") -> Any:
        return self._post(
            "configuration",
            {
                "language": language,
                "currentNavigation": {"code": code},
            },
        )

    def filter_groups(
        self,
        code: str,
        filter_values_selected: list[dict[str, Any]] | None = None,
        user_action: dict[str, str] | None = None,
        language: str = "nl-NL",
    ) -> Any:
        return self._post(
            "filter-groups",
            {
                "currentNavigation": {"code": code},
                "language": language,
                "filterValuesSelected": filter_values_selected or [],
                "userAction": user_action or {"code": "restart", "value": ""},
            },
        )

    def data(self, body: dict[str, Any]) -> Any:
        return self._post("data", body)

    def example_stage_distribution(self, year: int = 2024) -> Any:
        return self.data(
            {
                "language": "nl-NL",
                "navigation": {"code": "incidentie/verdeling-per-stadium"},
                "groupBy": [
                    {
                        "code": "filter/stadium",
                        "values": [
                            {"code": "stadium/0"},
                            {"code": "stadium/i"},
                            {"code": "stadium/ii"},
                            {"code": "stadium/iii"},
                            {"code": "stadium/iv"},
                            {"code": "stadium/x"},
                            {"code": "stadium/nvt"},
                        ],
                    }
                ],
                "aggregateBy": [
                    {
                        "code": "filter/kankersoort",
                        "values": [{"code": "kankersoort/totaal/alle"}],
                    },
                    {
                        "code": "filter/periode-van-diagnose",
                        "values": [{"code": f"periode/1-jaar/{year}"}],
                    },
                    {
                        "code": "filter/geslacht",
                        "values": [{"code": "geslacht/totaal/alle"}],
                    },
                    {
                        "code": "filter/leeftijdsgroep",
                        "values": [{"code": "leeftijdsgroep/totaal/alle"}],
                    },
                    {
                        "code": "filter/regio",
                        "values": [{"code": "regio/totaal/alle"}],
                    },
                ],
                "statistic": {"code": "statistiek/verdeling"},
            }
        )
