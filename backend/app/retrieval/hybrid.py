"""Hybrid medical retriever: structured-first, then vector, with medical safety."""

from __future__ import annotations

import logging
import re
from typing import Any

from app.config import Settings
from app.connectors.kankeratlas import KankerAtlasClient
from app.connectors.nkr_cijfers import NKRCijfersClient
from app.models import (
    Audience,
    Provenance,
    RetrievalResponse,
    SearchHit,
    SourceDocument,
)
from app.retrieval.simple import FIRST_PERSON_PATTERNS, UNSAFE_PATTERNS
from app.safety.abstention import check_evidence_threshold
from app.safety.red_flags import check_red_flags
from app.safety.source_policy import get_publisher_note, validate_source
from app.vectorstore.embedder import Embedder
from app.vectorstore.qdrant_store import QdrantStore

logger = logging.getLogger(__name__)

# Keywords that suggest the user wants statistics / numbers
STATS_KEYWORDS = [
    "hoeveel",
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

# Keywords that suggest a geographic / regional query
GEO_KEYWORDS = [
    "regio",
    "postcode",
    "pc3",
    "stad",
    "gemeente",
    "provincie",
    "atlas",
    "regionaal",
    "regionalen",
]

# Pattern to detect 3-4 digit postcode-like numbers
_POSTCODE_RE = re.compile(r"\b\d{3,4}\b")

# Pattern to detect year-like 4-digit numbers (1900-2099)
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


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
        validated_hits: list[SearchHit] = []
        for hit in vector_hits:
            source_id = hit.document.source_id
            if not validate_source(source_id):
                notes.append(f"Source '{source_id}' not in approved whitelist; hit excluded.")
                continue
            pub_note = get_publisher_note(source_id)
            if pub_note and pub_note not in notes:
                notes.append(pub_note)
            validated_hits.append(hit)

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

    # ------------------------------------------------------------------
    # Structured routing (APIs beat embeddings for exactness)
    # ------------------------------------------------------------------

    def _route_structured(self, query: str) -> list[SearchHit]:
        query_lower = query.lower()

        # --- Stats / NKR routing ---
        has_stats_kw = any(kw in query_lower for kw in STATS_KEYWORDS)
        has_year = bool(_YEAR_RE.search(query))
        if has_stats_kw or has_year:
            try:
                return self._fetch_nkr(query_lower)
            except Exception:
                logger.exception("NKR API call failed; falling through to vector search")

        # --- Geographic / Cancer Atlas routing ---
        has_geo_kw = any(kw in query_lower for kw in GEO_KEYWORDS)
        has_postcode = bool(_POSTCODE_RE.search(query))
        if has_geo_kw or has_postcode:
            try:
                return self._fetch_kankeratlas(query_lower)
            except Exception:
                logger.exception("Cancer Atlas API call failed; falling through to vector search")

        return []

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

        stage_data = self.nkr.example_stage_distribution()
        text = str(stage_data)[:4000]
        excerpt = (
            "Structured NKR response fetched for incidence distribution per stadium "
            "for all cancers in 2024."
        )
        return [
            self._build_structured_hit(
                source_id="nkr-cijfers",
                title="NKR Cijfers incidence distribution per stadium",
                url="https://nkr-cijfers.iknl.nl/viewer/incidentie-verdeling-per-stadium",
                text=text,
                excerpt=excerpt,
            )
        ]

    def _fetch_kankeratlas(self, query_lower: str) -> list[SearchHit]:
        """Fetch Cancer Atlas regional data."""
        atlas = self.kankeratlas.cancer_data(11, 3, 3)
        rows = atlas.get("res", [])[:5]
        excerpt = "Top sample postcode rows from the lung-cancer atlas: " + ", ".join(
            f"{row['postcode']} (p50={row['p50']})"
            for row in rows
            if isinstance(row, dict) and "postcode" in row and "p50" in row
        )
        return [
            self._build_structured_hit(
                source_id="kankeratlas",
                title="Cancer Atlas lung cancer incidence by postcode",
                url="https://kankeratlas.iknl.nl",
                text=str(rows),
                excerpt=excerpt,
            )
        ]

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
