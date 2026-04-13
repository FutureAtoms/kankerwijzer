"""Hybrid medical retriever: structured-first, then vector, with medical safety."""

from __future__ import annotations

import logging
import re
from typing import Any

from app.config import Settings
from app.connectors.firecrawl_client import FirecrawlClient
from app.connectors.kankeratlas import KankerAtlasClient
from app.connectors.nkr_cijfers import NKRCijfersClient
from app.connectors.richtlijnendatabase import RichtlijnendatabaseConnector
from app.models import (
    Audience,
    Provenance,
    RetrievalResponse,
    SearchHit,
    SourceDocument,
)
from app.retrieval.simple import FIRST_PERSON_PATTERNS, UNSAFE_PATTERNS
from app.safety.abstention import check_evidence_threshold, check_low_coverage
from app.safety.red_flags import check_red_flags, get_routing_info
from app.safety.source_policy import get_publisher_note, validate_source
from app.vectorstore.embedder import Embedder
from app.vectorstore.qdrant_store import QdrantStore

logger = logging.getLogger(__name__)

# Keywords that suggest the user wants statistics / numbers
STATS_KEYWORDS = [
    "hoeveel",
    "hoe vaak",
    "komt het voor",
    "aantal",
    "incidentie",
    "prevalentie",
    "overleving",
    "statistiek",
    "cijfers",
    "stadium",
    "verdeling",
    "percentage",
    "mortaliteit",
    "sterfte",
]

STAT_TYPE_KEYWORDS: dict[str, list[str]] = {
    "stadiumverdeling": [
        "stage distribution",
        "stadiumverdeling",
        "verdeling per stadium",
        "distribution per stadium",
    ],
    "overleving": [
        "overleving",
        "survival",
        "5-year survival",
        "5 jaarsoverleving",
        "5-jaars",
    ],
    "sterfte": [
        "sterfte",
        "mortaliteit",
        "mortality",
        "deaths",
        "death rate",
    ],
    "prevalentie": [
        "prevalentie",
        "prevalence",
    ],
    "incidentie": [
        "incidentie",
        "hoeveel",
        "hoe vaak",
        "komt het voor",
        "aantal",
        "how many",
        "new cases",
        "new diagnoses",
        "diagnoses",
        "gevallen",
    ],
}

# Keywords that suggest a geographic / regional query
GEO_KEYWORDS = [
    "regio",
    "postcode",
    "pc3",
    "gemeente",
    "provincie",
    "atlas",
    "regionaal",
    "regionalen",
]

IN_SCOPE_KEYWORDS = [
    # Dutch
    "kanker", "tumor", "oncolog", "chemotherapie", "chemo",
    "immunotherapie", "bestraling", "radiotherapie", "operatie",
    "behandeling", "bijwerking", "symptoom", "diagnose", "uitzaai",
    "stadium", "screening", "onderzoek", "coloscopie", "mammo",
    "borst", "darm", "long", "prostaat", "melanoom", "huidkanker",
    "lastmeter", "vermoeid", "misselijk", "pijn", "nkr",
    "incidentie", "overleving", "sterfte", "richtlijn", "atlas", "postcode",
    # English
    "cancer", "oncology", "tumor", "tumour", "chemotherapy",
    "immunotherapy", "radiation", "surgery", "treatment", "side effect",
    "symptom", "diagnosis", "metasta", "staging", "screening",
    "breast", "lung", "colon", "colorectal", "prostate", "melanoma",
    "skin cancer", "lymphoma", "leukemia", "leukaemia",
    "survival", "incidence", "mortality", "prevalence", "guideline",
    "carcinoma", "sarcoma", "myeloma", "blastoma",
]

# Pattern to detect 3-4 digit postcode-like numbers
_POSTCODE_RE = re.compile(r"\b\d{3,4}\b")

# Pattern to detect year-like 4-digit numbers (1900-2099)
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")

NKR_VIEWER_URLS: dict[str, str] = {
    "incidentie": "https://nkr-cijfers.iknl.nl/viewer/incidentie-per-jaar",
    "prevalentie": "https://nkr-cijfers.iknl.nl/viewer/prevalentie-per-jaar",
    "sterfte": "https://nkr-cijfers.iknl.nl/viewer/sterfte-per-jaar",
    "overleving": "https://nkr-cijfers.iknl.nl/viewer/overleving-per-jaar",
    "stadiumverdeling": "https://nkr-cijfers.iknl.nl/viewer/incidentie-verdeling-per-stadium",
}

CANCER_TYPE_ALIASES: dict[str, tuple[str, ...]] = {
    "alle": ("alle kankersoorten", "all cancers", "all cancer types"),
    "borstkanker": ("borstkanker", "breast cancer"),
    "longkanker": ("longkanker", "lung cancer"),
    "darmkanker": ("darmkanker", "colon cancer", "bowel cancer", "colorectal cancer"),
    "dikkedarmkanker": ("dikkedarmkanker", "colonkanker", "coloncarcinoom", "colon carcinoma"),
    "endeldarmkanker": ("endeldarmkanker", "rectal cancer"),
    "prostaatkanker": ("prostaatkanker", "prostate cancer", "prostate carcinoma"),
    "blaaskanker": ("blaaskanker", "bladder cancer"),
    "nierkanker": ("nierkanker", "kidney cancer", "renal cancer"),
    "melanoom": ("melanoom", "melanoma"),
    "huidkanker": ("huidkanker", "skin cancer"),
    "maagkanker": ("maagkanker", "stomach cancer", "gastric cancer"),
    "slokdarmkanker": ("slokdarmkanker", "esophageal cancer", "oesophageal cancer"),
    "alvleesklierkanker": ("alvleesklierkanker", "pancreatic cancer"),
    "leverkanker": ("leverkanker", "liver cancer"),
    "eierstokkanker": ("eierstokkanker", "ovarian cancer"),
    "baarmoederhalskanker": ("baarmoederhalskanker", "cervical cancer"),
    "baarmoederkanker": ("baarmoederkanker", "endometrial cancer", "uterine cancer"),
    "schildklierkanker": ("schildklierkanker", "thyroid cancer"),
    "leukemie": ("leukemie", "leukemia"),
    "hodgkinlymfoom": ("hodgkinlymfoom", "hodgkin lymphoma"),
    "non-hodgkinlymfoom": ("non-hodgkinlymfoom", "non-hodgkin lymphoma"),
    "hersenkanker": ("hersenkanker", "brain cancer"),
    "keelkanker": ("keelkanker", "throat cancer"),
}

SEX_ALIASES: dict[str, tuple[str, ...]] = {
    "vrouw": ("vrouw", "vrouwen", "female", "women", "woman"),
    "man": ("man", "mannen", "male", "men"),
}

STAGE_ALIASES: dict[str, tuple[str, ...]] = {
    "0": ("stadium 0", "stage 0"),
    "i": ("stadium i", "stadium 1", "stage i", "stage 1"),
    "ii": ("stadium ii", "stadium 2", "stage ii", "stage 2"),
    "iii": ("stadium iii", "stadium 3", "stage iii", "stage 3"),
    "iv": ("stadium iv", "stadium 4", "stage iv", "stage 4"),
}

ATLAS_CANCER_GROUPS: dict[str, dict[str, Any]] = {
    "alle": {"group": 1, "label": "alle kankersoorten", "validsex": 3, "pc4": False},
    "alvleesklierkanker": {
        "group": 2,
        "label": "alvleesklierkanker en periampullaire kanker",
        "validsex": 3,
        "pc4": False,
    },
    "baarmoederhalskanker": {"group": 3, "label": "baarmoederhalskanker", "validsex": 2, "pc4": False},
    "blaaskanker": {"group": 4, "label": "blaaskanker en kanker van de urinewegen", "validsex": 3, "pc4": False},
    "borstkanker": {"group": 5, "label": "borstkanker", "validsex": 2, "pc4": False},
    "darmkanker": {"group": 6, "label": "darmkanker", "validsex": 3, "pc4": False},
    "dikkedarmkanker": {"group": 6, "label": "darmkanker", "validsex": 3, "pc4": False},
    "endeldarmkanker": {"group": 6, "label": "darmkanker", "validsex": 3, "pc4": False},
    "eierstokkanker": {"group": 7, "label": "eierstokkanker", "validsex": 2, "pc4": False},
    "baarmoederkanker": {"group": 8, "label": "baarmoederkanker", "validsex": 2, "pc4": False},
    "keelkanker": {"group": 9, "label": "hoofd-halskanker", "validsex": 3, "pc4": False},
    "leverkanker": {"group": 10, "label": "leverkanker en galwegkanker", "validsex": 3, "pc4": False},
    "longkanker": {"group": 11, "label": "longkanker", "validsex": 3, "pc4": True},
    "leukemie": {"group": 12, "label": "lymfomen en lymfatische leukemie", "validsex": 3, "pc4": False},
    "hodgkinlymfoom": {"group": 12, "label": "lymfomen en lymfatische leukemie", "validsex": 3, "pc4": False},
    "non-hodgkinlymfoom": {"group": 12, "label": "lymfomen en lymfatische leukemie", "validsex": 3, "pc4": False},
    "maagkanker": {"group": 13, "label": "maagkanker", "validsex": 3, "pc4": False},
    "hersenkanker": {
        "group": 14,
        "label": "maligne tumoren van het centraal zenuwstelsel",
        "validsex": 3,
        "pc4": False,
    },
    "melanoom": {"group": 15, "label": "huidkanker - melanoom", "validsex": 3, "pc4": False},
    "huidkanker": {"group": 15, "label": "huidkanker - melanoom", "validsex": 3, "pc4": False},
    "nierkanker": {"group": 19, "label": "nierkanker", "validsex": 3, "pc4": False},
    "prostaatkanker": {"group": 22, "label": "prostaatkanker", "validsex": 1, "pc4": False},
    "schildklierkanker": {"group": 24, "label": "schildklierkanker", "validsex": 3, "pc4": False},
    "slokdarmkanker": {"group": 25, "label": "slokdarmkanker", "validsex": 3, "pc4": False},
}

ATLAS_SEX_CODES = {"man": 1, "vrouw": 2, "alle": 3}
ATLAS_SEX_LABELS = {1: "mannen", 2: "vrouwen", 3: "alle personen"}


class HybridMedicalRetriever:
    """Structured-first, then vector, with medical safety.

    Pipeline order:
    1. Red-flag detection (emergency / crisis / treatment / diagnosis)
    2. Legacy unsafe-pattern detection (from simple.py)
    3. Structured-first routing (NKR stats API, Cancer Atlas API)
    4. Vector search via Qdrant
    5. Evidence-threshold abstention
    6. Source-whitelist validation
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.nkr = NKRCijfersClient(settings)
        self.kankeratlas = KankerAtlasClient(settings)
        self.richtlijn = RichtlijnendatabaseConnector(FirecrawlClient(settings))

        # Lazy-init for heavy dependencies (model loading)
        self._embedder: Embedder | None = None
        self._qdrant: QdrantStore | None = None

    # ------------------------------------------------------------------
    # Lazy initialisation helpers
    # ------------------------------------------------------------------

    @property
    def embedder(self) -> Embedder:
        if self._embedder is None:
            self._embedder = Embedder()
        return self._embedder

    @property
    def qdrant(self) -> QdrantStore:
        if self._qdrant is None:
            self._qdrant = QdrantStore()
        return self._qdrant

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        audience: Audience = "patient",
        limit: int = 5,
    ) -> RetrievalResponse:
        notes: list[str] = []

        # ---- 1. Red-flag detection ------------------------------------
        flag_type, routing_msg = check_red_flags(query)
        if flag_type in ("emergency", "crisis"):
            return RetrievalResponse(
                query=query,
                audience=audience,
                refusal_reason=routing_msg,
                notes=[f"Red-flag detected: {flag_type}"],
            )
        if flag_type in ("treatment_decision", "diagnosis"):
            return RetrievalResponse(
                query=query,
                audience=audience,
                refusal_reason=routing_msg,
                notes=[f"Red-flag detected: {flag_type}"],
            )

        # ---- 1.5 Distress/wellbeing detection (Lastmeter bypass) ------
        # If the user is expressing distress symptoms, let it through to
        # the agent so the Lastmeter tool can handle it conversationally.
        if self._is_distress_query(query):
            # Skip legacy patterns — the agent's Lastmeter tool will handle this
            pass
        else:
            if not self._is_in_scope_query(query):
                return RetrievalResponse(
                    query=query,
                    audience=audience,
                    refusal_reason="Deze vraag valt buiten het onderwerp kanker en oncologische informatie.",
                    notes=["Out-of-scope query detected before retrieval."],
                )

            # ---- 2. Legacy unsafe-pattern detection -----------------------
            legacy_refusal = self._check_legacy_patterns(query)
            if legacy_refusal:
                return RetrievalResponse(
                    query=query,
                    audience=audience,
                    refusal_reason=legacy_refusal,
                    notes=["Unsafe prompt detected by legacy pattern matcher."],
                )

        # ---- 3. Structured-first routing ------------------------------
        structured_hits = self._route_structured(query)
        if structured_hits:
            if self._should_augment_structured_hits(query):
                notes.append("Structured API routing handled the statistics portion of this query.")
                try:
                    vector_hits = self._vector_search(query, limit=max(limit, 5))
                except Exception:
                    logger.exception("Vector search failed while augmenting structured evidence")
                    vector_hits = []
                    notes.append("Vector search augmentation encountered an error; using structured evidence only.")
                structured_hits = self._merge_hits(
                    structured_hits,
                    self._validate_hits(vector_hits, notes),
                )
                notes.append("Added vector evidence for explanatory context.")
            else:
                notes.append("Structured API routing handled this query.")
            return RetrievalResponse(
                query=query,
                audience=audience,
                hits=structured_hits[:limit],
                notes=notes,
            )

        # ---- 4. Vector search ----------------------------------------
        try:
            vector_hits = self._vector_search(query, limit=limit)
        except Exception:
            logger.exception("Vector search failed")
            vector_hits = []
            notes.append("Vector search encountered an error; falling back to empty results.")

        # ---- 4.5 Low-coverage refusal for specific cancer types ------
        low_coverage = check_low_coverage(query, vector_hits)
        if low_coverage:
            notes.append("Requested cancer type is not supported by the retrieved evidence.")
            return RetrievalResponse(
                query=query,
                audience=audience,
                refusal_reason="Onvoldoende bewijs gevonden voor deze specifieke kankersoort.",
                notes=notes,
            )

        # ---- 5. Evidence-threshold abstention -------------------------
        refusal = check_evidence_threshold(vector_hits, self.settings.abstention_threshold)
        if refusal:
            notes.append(
                f"Top score below abstention threshold ({self.settings.abstention_threshold})."
            )
            return RetrievalResponse(
                query=query,
                audience=audience,
                refusal_reason="Onvoldoende bewijs gevonden om deze vraag betrouwbaar te beantwoorden.",
                notes=notes,
            )

        # ---- 6. Source-whitelist + publisher notes ---------------------
        validated_hits = self._validate_hits(vector_hits, notes)

        if not validated_hits:
            return RetrievalResponse(
                query=query,
                audience=audience,
                refusal_reason="Onvoldoende bewijs gevonden om deze vraag betrouwbaar te beantwoorden.",
                notes=notes + ["All retrieved sources were filtered by whitelist policy."],
            )

        return RetrievalResponse(
            query=query,
            audience=audience,
            hits=validated_hits[:limit],
            notes=notes,
        )

    # ------------------------------------------------------------------
    # Legacy pattern matching (from simple.py)
    # ------------------------------------------------------------------

    @staticmethod
    def _is_distress_query(query: str) -> bool:
        """Detect if the query expresses patient distress/wellbeing concerns.

        These should bypass legacy safety patterns and be handled by the
        agent's Lastmeter tool instead of being refused.
        """
        distress_keywords = [
            "moe", "vermoeid", "pijn", "slaap", "slecht slapen",
            "angst", "angstig", "bang", "zorgen", "somber", "depressief",
            "eenzaam", "alleen", "verdrietig", "boos", "gefrustreerd",
            "misselijk", "eetlust", "gewicht", "benauwd",
            "last", "klachten", "hoe voel", "moeilijk", "zwaar",
            "hulp nodig", "niet meer", "stress", "gespannen",
            "lastmeter", "distress",
        ]
        q = query.lower()
        return sum(1 for kw in distress_keywords if kw in q) >= 2

    @staticmethod
    def _check_legacy_patterns(query: str) -> str | None:
        query_lower = f" {query.lower()} "
        for pattern in UNSAFE_PATTERNS:
            if pattern in query_lower:
                return (
                    "This system should refuse personalized diagnosis or treatment advice "
                    "and redirect the user to a clinician."
                )
        if any(token in query_lower for token in FIRST_PERSON_PATTERNS) and (
            "should i" in query_lower
            or "what should i do" in query_lower
            or "chemotherapy" in query_lower
            or "behandeling" in query_lower
        ):
            return (
                "This system should refuse personalized diagnosis or treatment advice "
                "and redirect the user to a clinician."
            )
        return None

    @staticmethod
    def _is_in_scope_query(query: str) -> bool:
        query_lower = query.lower()
        # Check scope keywords
        if any(keyword in query_lower for keyword in IN_SCOPE_KEYWORDS):
            return True
        # Check cancer type aliases (bidirectional: alias in query OR query words in alias)
        query_words = set(query_lower.split())
        for aliases in CANCER_TYPE_ALIASES.values():
            for alias in aliases:
                if alias in query_lower:
                    return True
                # Also check if any query word appears in the alias
                alias_words = set(alias.split())
                if query_words & alias_words:
                    return True
        return False

    @staticmethod
    def _should_augment_structured_hits(query: str) -> bool:
        query_lower = query.lower()
        asks_for_statistics = any(keyword in query_lower for keyword in STATS_KEYWORDS)
        asks_for_explanation = any(
            keyword in query_lower
            for keyword in (
                "wat is",
                "what is",
                "uitleg",
                "leg uit",
                "sympt",
                "behandeling",
                "risicofactor",
            )
        )
        return asks_for_statistics and asks_for_explanation

    @staticmethod
    def _merge_hits(primary_hits: list[SearchHit], extra_hits: list[SearchHit]) -> list[SearchHit]:
        merged = list(primary_hits)
        seen_keys = {
            (hit.document.source_id, hit.document.url or hit.document.title)
            for hit in primary_hits
        }
        for hit in extra_hits:
            key = (hit.document.source_id, hit.document.url or hit.document.title)
            if key in seen_keys:
                continue
            merged.append(hit)
            seen_keys.add(key)
        return merged

    @staticmethod
    def _validate_hits(hits: list[SearchHit], notes: list[str]) -> list[SearchHit]:
        validated_hits: list[SearchHit] = []
        for hit in hits:
            source_id = hit.document.source_id
            if not validate_source(source_id):
                notes.append(f"Source '{source_id}' not in approved whitelist; hit excluded.")
                continue
            pub_note = get_publisher_note(source_id)
            if pub_note and pub_note not in notes:
                notes.append(pub_note)
            validated_hits.append(hit)
        return validated_hits

    # ------------------------------------------------------------------
    # Structured routing (APIs beat embeddings for exactness)
    # ------------------------------------------------------------------

    def _route_structured(self, query: str) -> list[SearchHit]:
        query_lower = query.lower()

        # --- Guideline routing ---
        if "richtlijn" in query_lower or "guideline" in query_lower:
            try:
                return self._fetch_richtlijn(query_lower)
            except Exception:
                logger.exception("Guideline fetch failed; falling through to other routes")

        # --- Geographic / Cancer Atlas routing ---
        has_year = bool(_YEAR_RE.search(query))
        has_geo_kw = any(kw in query_lower for kw in GEO_KEYWORDS)
        postcode_tokens = _POSTCODE_RE.findall(query)
        has_postcode = any(not _YEAR_RE.fullmatch(token) for token in postcode_tokens)
        if has_geo_kw or has_postcode:
            try:
                return self._fetch_kankeratlas(query_lower)
            except Exception:
                logger.exception("Cancer Atlas API call failed; falling through to vector search")

        # --- Stats / NKR routing ---
        has_stats_kw = any(kw in query_lower for kw in STATS_KEYWORDS)
        if has_stats_kw or has_year:
            try:
                return self._fetch_nkr(query_lower)
            except Exception:
                logger.exception("NKR API call failed; falling through to vector search")

        return []

    def _fetch_richtlijn(self, query_lower: str) -> list[SearchHit]:
        """Fetch a guideline overview page from Richtlijnendatabase."""
        guideline = self.richtlijn.scrape_guideline()
        if isinstance(guideline, dict):
            markdown = guideline.get("markdown", "")
            title = guideline.get("metadata", {}).get("title") or "Richtlijnendatabase"
            url = guideline.get("url") or self.richtlijn.EXAMPLE_GUIDELINE
        else:
            markdown = getattr(guideline, "markdown", "") or ""
            metadata = getattr(guideline, "metadata", None)
            title = getattr(metadata, "title", None) or "Richtlijnendatabase"
            url = getattr(metadata, "url", None) or self.richtlijn.EXAMPLE_GUIDELINE
        excerpt = markdown[:400].replace("\n", " ").strip() or title
        return [
            self._build_structured_hit(
                source_id="richtlijnendatabase",
                title=title,
                url=url,
                text=markdown or title,
                excerpt=excerpt,
            )
        ]

    def _fetch_nkr(self, query_lower: str) -> list[SearchHit]:
        """Fetch NKR statistics data."""
        if "navigation" in query_lower:
            navigation = self.nkr.navigation_items()
            items = navigation.get("items", [])
            top_labels: list[str] = []
            if items and isinstance(items[0], dict):
                top_labels = [child["label"] for child in items[0].get("children", [])[:5]]
            text = "Available NKR topics: " + ", ".join(top_labels)
            return [
                self._build_structured_hit(
                    source_id="nkr-cijfers",
                    title="NKR Cijfers navigation",
                    url="https://nkr-cijfers.iknl.nl",
                    text=text,
                    excerpt=text,
                )
            ]

        stats_request = self._parse_nkr_request(query_lower)
        data = self.nkr.query_statistics(**stats_request)
        title = self._nkr_title_for_request(stats_request, data)
        excerpt = self._nkr_excerpt_for_request(stats_request, data)
        return [
            self._build_structured_hit(
                source_id="nkr-cijfers",
                title=title,
                url=NKR_VIEWER_URLS.get(stats_request["stat_type"], "https://nkr-cijfers.iknl.nl"),
                text=str(data)[:4000],
                excerpt=excerpt,
            )
        ]

    def _fetch_kankeratlas(self, query_lower: str) -> list[SearchHit]:
        """Fetch Cancer Atlas regional data."""
        atlas_request = self._parse_kankeratlas_request(query_lower)
        atlas = self.kankeratlas.cancer_data(
            atlas_request["cancer_group"],
            atlas_request["sex"],
            atlas_request["postcode_digits"],
        )
        rows = atlas.get("res", [])[:5] if isinstance(atlas, dict) else []
        title = (
            f"Kanker Atlas {atlas_request['cancer_label'].title()} "
            f"per PC{atlas_request['postcode_digits']}"
        )
        excerpt = self._kankeratlas_excerpt_for_request(atlas_request, rows)
        return [
            self._build_structured_hit(
                source_id="kankeratlas",
                title=title,
                url="https://kankeratlas.iknl.nl",
                text=str(rows),
                excerpt=excerpt,
            )
        ]

    @staticmethod
    def _extract_year(query: str) -> int:
        years = re.findall(r"\b(?:19|20)\d{2}\b", query)
        if years:
            return int(years[-1])
        return 2024

    @staticmethod
    def _extract_sex(query: str) -> str:
        for sex, aliases in SEX_ALIASES.items():
            if any(alias in query for alias in aliases):
                return sex
        return "alle"

    @staticmethod
    def _extract_cancer_type(query: str) -> str:
        for cancer_type, aliases in CANCER_TYPE_ALIASES.items():
            if any(alias in query for alias in aliases):
                return cancer_type
        return "alle"

    @staticmethod
    def _extract_stat_type(query: str) -> str:
        for stat_type, keywords in STAT_TYPE_KEYWORDS.items():
            if any(keyword in query for keyword in keywords):
                return stat_type
        return "incidentie"

    def _parse_nkr_request(self, query: str) -> dict[str, Any]:
        return {
            "cancer_type": self._extract_cancer_type(query),
            "year": self._extract_year(query),
            "sex": self._extract_sex(query),
            "stat_type": self._extract_stat_type(query),
            "stage": self._extract_stage(query),
        }

    def _parse_kankeratlas_request(self, query: str) -> dict[str, Any]:
        cancer_type = self._extract_cancer_type(query)
        atlas_group = ATLAS_CANCER_GROUPS.get(cancer_type, ATLAS_CANCER_GROUPS["alle"])
        requested_sex = ATLAS_SEX_CODES.get(self._extract_sex(query), 3)
        sex = atlas_group["validsex"] if atlas_group["validsex"] in (1, 2) else requested_sex

        postcode_tokens = [
            token for token in _POSTCODE_RE.findall(query) if not _YEAR_RE.fullmatch(token)
        ]
        postcode_digits = 3
        if atlas_group["pc4"] and (
            "pc4" in query
            or "4-cijfer" in query
            or "4 digit" in query
            or any(len(token) == 4 for token in postcode_tokens)
        ):
            postcode_digits = 4
        if "pc3" in query or "3-cijfer" in query or "3 digit" in query:
            postcode_digits = 3

        return {
            "cancer_group": atlas_group["group"],
            "cancer_label": atlas_group["label"],
            "sex": sex,
            "postcode_digits": postcode_digits,
        }

    @staticmethod
    def _extract_stage(query: str) -> str:
        query_lower = query.lower()
        ordered_aliases = sorted(
            STAGE_ALIASES.items(),
            key=lambda item: max(len(alias) for alias in item[1]),
            reverse=True,
        )
        for stage, aliases in ordered_aliases:
            if any(alias in query_lower for alias in aliases):
                return stage
        return "alle"

    @staticmethod
    def _nkr_title_for_request(request: dict[str, Any], data: dict[str, Any]) -> str:
        title = data.get("title", {}) if isinstance(data, dict) else {}
        if isinstance(title, dict) and title.get("title"):
            return str(title["title"])
        stat_type = request["stat_type"]
        cancer_type = request["cancer_type"]
        year = request["year"]
        return f"NKR Cijfers {stat_type} voor {cancer_type} in {year}"

    @staticmethod
    def _nkr_excerpt_for_request(request: dict[str, Any], data: dict[str, Any]) -> str:
        stat_type = request["stat_type"]
        cancer_type = request["cancer_type"]
        year = request["year"]
        sex = request["sex"]
        stage = request.get("stage", "alle")

        data_rows = data.get("data", []) if isinstance(data, dict) else []
        readable_cancer = cancer_type.replace("kanker", "kanker").replace("-", " ")
        readable_sex = {
            "alle": "alle personen",
            "vrouw": "vrouwen",
            "man": "mannen",
        }.get(sex, sex)
        readable_stage = f", stadium {stage.upper()}" if stage != "alle" else ""

        if stat_type == "stadiumverdeling":
            parts: list[str] = []
            for row in data_rows[:7]:
                filter_values = row.get("filterValues", [])
                stage_code = ""
                if filter_values and isinstance(filter_values[0], dict):
                    stage_code = filter_values[0].get("code", "")
                stage = stage_code.split("/")[-1].upper() if stage_code else "onbekend"
                value = row.get("value")
                if value is not None:
                    parts.append(f"{stage}: {value}%")
            summary = ", ".join(parts) if parts else "geen data"
            return (
                f"Stadiumverdeling in {year} voor {readable_sex} met {readable_cancer}: {summary}."
            )

        first = data_rows[0] if data_rows else {}
        value = first.get("value")
        metric_label = {
            "incidentie": "nieuwe diagnoses",
            "prevalentie": "prevalente gevallen",
            "sterfte": "sterfgevallen",
            "overleving": "5-jaarsoverleving",
        }.get(stat_type, stat_type)
        if value is None:
            return (
                f"NKR respons voor {readable_cancer}{readable_stage} "
                f"({metric_label}) in {year} voor {readable_sex}."
            )
        if stat_type == "overleving":
            return (
                f"{metric_label.capitalize()} in {year} voor {readable_sex} "
                f"met {readable_cancer}{readable_stage}: {value}%."
            )
        return (
            f"{metric_label.capitalize()} in {year} voor {readable_sex} "
            f"met {readable_cancer}{readable_stage}: {int(value)}."
        )

    @staticmethod
    def _kankeratlas_excerpt_for_request(
        request: dict[str, Any], rows: list[dict[str, Any]]
    ) -> str:
        sex_label = ATLAS_SEX_LABELS.get(request["sex"], "alle personen")
        cancer_label = request["cancer_label"]
        postcode_level = f"PC{request['postcode_digits']}"
        samples = [
            f"{row['postcode']} (p50={row['p50']})"
            for row in rows
            if isinstance(row, dict) and "postcode" in row and "p50" in row
        ]
        if not samples:
            return (
                f"Regionale atlasdata voor {sex_label} met {cancer_label} "
                f"op {postcode_level}-niveau."
            )
        return (
            f"Regionale atlasdata voor {sex_label} met {cancer_label} "
            f"op {postcode_level}-niveau. Voorbeelden: {', '.join(samples)}."
        )

    # ------------------------------------------------------------------
    # Vector search
    # ------------------------------------------------------------------

    def _vector_search(self, query: str, limit: int = 5) -> list[SearchHit]:
        query_vector = self.embedder.embed_query(query)
        raw_hits = self.qdrant.search(query_vector=query_vector, top_k=limit)
        return [self._qdrant_hit_to_search_hit(h) for h in raw_hits if h.get("text")]

    # ------------------------------------------------------------------
    # Hit builders
    # ------------------------------------------------------------------

    @staticmethod
    def _qdrant_hit_to_search_hit(hit: dict[str, Any]) -> SearchHit:
        text = hit.get("text") or ""
        source_id = hit.get("source_id") or "unknown"
        title = hit.get("title") or ""
        citation_url = hit.get("citation_url") or ""

        prov = Provenance(
            source_id=source_id,
            title=title,
            url=citation_url,
            canonical_url=hit.get("canonical_url"),
            document_id=hit.get("document_id"),
            chunk_id=hit.get("chunk_id"),
            page_number=hit.get("page_number"),
            section=hit.get("section"),
            excerpt=text[:200],
            checksum=hit.get("checksum"),
        )
        doc = SourceDocument(
            document_id=hit.get("document_id") or "",
            source_id=source_id,
            title=title,
            url=citation_url,
            content_type="text",
            text=text,
            provenance=prov,
        )
        return SearchHit(score=hit.get("score", 0.0), excerpt=text[:300], document=doc)

    @staticmethod
    def _build_structured_hit(
        *,
        source_id: str,
        title: str,
        url: str,
        text: str,
        excerpt: str,
    ) -> SearchHit:
        publisher = "IKNL" if source_id != "richtlijnendatabase" else "Richtlijnendatabase"
        prov = Provenance(
            source_id=source_id,
            title=title,
            url=url,
            canonical_url=url,
            publisher=publisher,
            excerpt=excerpt,
        )
        doc = SourceDocument(
            document_id=url,
            source_id=source_id,
            title=title,
            url=url,
            content_type="text/plain",
            text=text,
            provenance=prov,
        )
        return SearchHit(score=1.0, excerpt=excerpt, document=doc)
