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

    # -----------------------------------------------------------------
    # Cancer type code mapping (common cancers → NKR API codes)
    # -----------------------------------------------------------------
    CANCER_TYPE_CODES: dict[str, str] = {
        "alle": "kankersoort/totaal/alle",
        "borstkanker": "kankersoort/hoofdgroep/500000",
        "mammacarcinoom": "kankersoort/subgroep/501300",
        "longkanker": "kankersoort/subgroep/302000",
        "darmkanker": "kankersoort/subgroep/205000",
        "dikkedarmkanker": "kankersoort/205310",
        "endeldarmkanker": "kankersoort/205330",
        "prostaatkanker": "kankersoort/subgroep/702000",
        "blaaskanker": "kankersoort/subgroep/713000",
        "nierkanker": "kankersoort/subgroep/711000",
        "melanoom": "kankersoort/subgroep/441300",
        "huidkanker": "kankersoort/hoofdgroep/400000",
        "maagkanker": "kankersoort/subgroep/203000",
        "slokdarmkanker": "kankersoort/subgroep/201000",
        "alvleesklierkanker": "kankersoort/subgroep/209000",
        "leverkanker": "kankersoort/subgroep/207000",
        "eierstokkanker": "kankersoort/subgroep/606000",
        "baarmoederhalskanker": "kankersoort/subgroep/603000",
        "baarmoederkanker": "kankersoort/subgroep/604000",
        "schildklierkanker": "kankersoort/subgroep/901000",
        "leukemie": "kankersoort/subgroep/811000",
        "hodgkinlymfoom": "kankersoort/subgroep/801000",
        "non-hodgkinlymfoom": "kankersoort/subgroep/804000",
        "hersenkanker": "kankersoort/subgroep/950000",
        "keelkanker": "kankersoort/subgroep/103000",
    }

    # Sex filter mapping
    SEX_CODES: dict[str, str] = {
        "alle": "geslacht/totaal/alle",
        "man": "geslacht/man",
        "vrouw": "geslacht/vrouw",
    }

    STAGE_CODES: dict[str, str] = {
        "alle": "stadium/totaal/alle",
        "0": "stadium/0",
        "i": "stadium/i",
        "ii": "stadium/ii",
        "iii": "stadium/iii",
        "iv": "stadium/iv",
        "x": "stadium/x",
        "nvt": "stadium/nvt",
    }

    def query_statistics(
        self,
        cancer_type: str = "alle",
        year: int = 2024,
        sex: str = "alle",
        stat_type: str = "incidentie",
        stage: str = "alle",
    ) -> Any:
        """Query NKR statistics with specific filters.

        Args:
            cancer_type: Cancer type key (e.g. 'prostaatkanker', 'borstkanker').
            year: Diagnosis year.
            sex: 'alle', 'man', or 'vrouw'.
            stat_type: 'incidentie', 'stadiumverdeling', 'prevalentie', 'sterfte', 'overleving'.
            stage: Optional stage filter for survival queries.
        """
        cancer_code = self.CANCER_TYPE_CODES.get(
            cancer_type.lower(), self.CANCER_TYPE_CODES["alle"]
        )
        sex_code = self.SEX_CODES.get(sex.lower(), self.SEX_CODES["alle"])
        stage_code = self.STAGE_CODES.get(stage.lower(), self.STAGE_CODES["alle"])

        # Each stat type uses a different navigation + statistic code + groupBy
        st = stat_type.lower()

        if st == "stadiumverdeling":
            return self._query_stadiumverdeling(cancer_code, year, sex_code)
        elif st == "overleving":
            return self._query_overleving(cancer_code, year, sex_code, stage_code)
        elif st == "sterfte":
            return self._query_sterfte(cancer_code, year, sex_code)
        else:
            # incidentie and prevalentie use the same pattern
            return self._query_incidentie_type(st, cancer_code, year, sex_code)

    def _query_incidentie_type(
        self, stat_type: str, cancer_code: str, year: int, sex_code: str
    ) -> Any:
        """Query incidentie/prevalentie/sterfte — single year, single number."""
        nav_map = {
            "incidentie": "incidentie/periode",
            "prevalentie": "prevalentie/periode",
            "sterfte": "sterfte/periode",
        }
        nav_code = nav_map.get(stat_type, "incidentie/periode")

        return self.data({
            "language": "nl-NL",
            "navigation": {"code": nav_code},
            "groupBy": [
                {
                    "code": "filter/periode-van-diagnose",
                    "values": [{"code": f"periode/1-jaar/{year}"}],
                }
            ],
            "aggregateBy": [
                {
                    "code": "filter/kankersoort",
                    "values": [{"code": cancer_code}],
                },
                {
                    "code": "filter/geslacht",
                    "values": [{"code": sex_code}],
                },
                {
                    "code": "filter/leeftijdsgroep",
                    "values": [{"code": "leeftijdsgroep/totaal/alle"}],
                },
                {
                    "code": "filter/regio",
                    "values": [{"code": "regio/totaal/alle"}],
                },
                {
                    "code": "filter/stadium",
                    "values": [{"code": "stadium/totaal/alle"}],
                },
            ],
            "statistic": {"code": "statistiek/aantal"},
        })

    @staticmethod
    def _to_cbs_cancer_code(cancer_code: str) -> str:
        if cancer_code.startswith("kankersoort/"):
            return cancer_code.replace("kankersoort/", "kankersoortCBS/", 1)
        return cancer_code

    def _query_stadiumverdeling(
        self, cancer_code: str, year: int, sex_code: str
    ) -> Any:
        """Query stage distribution for a specific cancer type and year."""
        return self.data({
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
                    "values": [{"code": cancer_code}],
                },
                {
                    "code": "filter/periode-van-diagnose",
                    "values": [{"code": f"periode/1-jaar/{year}"}],
                },
                {
                    "code": "filter/geslacht",
                    "values": [{"code": sex_code}],
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
        })

    def _query_overleving(
        self, cancer_code: str, year: int, sex_code: str, stage_code: str
    ) -> Any:
        """Query 5-year relative survival for a specific cancer type.

        NKR survival data uses diagnosis-period buckets plus years-after-diagnosis
        instead of a single diagnosis year.
        """
        period_code = "periode/10-jaar/2015-2024"
        if year < 2015:
            period_code = "periode/10-jaar/2005-2014"

        return self.data({
            "language": "nl-NL",
            "navigation": {"code": "overleving/periode"},
            "groupBy": [
                {
                    "code": "filter/jaren-na-diagnose",
                    "values": [{"code": "jaren-na-diagnose/5"}],
                }
            ],
            "aggregateBy": [
                {
                    "code": "filter/kankersoort",
                    "values": [{"code": cancer_code}],
                },
                {
                    "code": "filter/geslacht",
                    "values": [{"code": sex_code}],
                },
                {
                    "code": "filter/periode-van-diagnose",
                    "values": [{"code": period_code}],
                },
                {
                    "code": "filter/leeftijdsgroep",
                    "values": [{"code": "leeftijdsgroep/totaal/alle"}],
                },
                {
                    "code": "filter/stadium",
                    "values": [{"code": stage_code}],
                },
            ],
            "statistic": {"code": "statistiek/relatieve-overleving"},
        })

    def _query_sterfte(
        self, cancer_code: str, year: int, sex_code: str
    ) -> Any:
        """Query mortality counts using the CBS-backed sterfte schema."""
        return self.data({
            "language": "nl-NL",
            "navigation": {"code": "sterfte/periode"},
            "groupBy": [
                {
                    "code": "filter/jaar-van-overlijden",
                    "values": [{"code": f"periode/1-jaar/{year}"}],
                }
            ],
            "aggregateBy": [
                {
                    "code": "filter/kankersoortCBS",
                    "values": [{"code": self._to_cbs_cancer_code(cancer_code)}],
                },
                {
                    "code": "filter/geslacht",
                    "values": [{"code": sex_code}],
                },
                {
                    "code": "filter/leeftijdsgroep",
                    "values": [{"code": "leeftijdsgroep/totaal/alle"}],
                },
            ],
            "statistic": {"code": "statistiek/aantal"},
        })

    def example_stage_distribution(self, year: int = 2024) -> Any:
        """Legacy helper — delegates to query_statistics."""
        return self.query_statistics(
            cancer_type="alle", year=year, stat_type="stadiumverdeling"
        )
