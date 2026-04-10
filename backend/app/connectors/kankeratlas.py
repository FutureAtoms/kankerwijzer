from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings


class KankerAtlasClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.filters_url = "https://kankeratlas.iknl.nl/locales/nl/filters.json?format=json"
        self.base_url = "https://iknl-atlas-strapi-prod.azurewebsites.net/api"

    def _get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        response = httpx.get(
            url,
            params=params,
            timeout=self.settings.request_timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def filters(self) -> Any:
        return self._get(self.filters_url)

    def cancer_groups(self, locale: str = "nl") -> Any:
        return self._get(
            f"{self.base_url}/cancer-groups/cancergrppc",
            params={"locale": locale},
        )

    def postcodes(self, digits: int = 3) -> Any:
        return self._get(f"{self.base_url}/postcodes/getbypc/{digits}")

    def cancer_data(self, cancer_group: int, sex: int, postcode_digits: int = 3) -> Any:
        return self._get(
            f"{self.base_url}/cancer-datas/getbygroupsexpostcode/"
            f"{cancer_group}/{sex}/{postcode_digits}"
        )
