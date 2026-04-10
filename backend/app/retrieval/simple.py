from __future__ import annotations

from app.config import Settings
from app.connectors.kankeratlas import KankerAtlasClient
from app.connectors.kanker_nl import LocalKankerNLDataset
from app.connectors.nkr_cijfers import NKRCijfersClient
from app.models import Audience, Provenance, RetrievalResponse, SearchHit, SourceDocument


UNSAFE_PATTERNS = [
    "diagnose me",
    "am i dying",
    "should i take",
    "which chemotherapy should i start",
    "personal treatment plan",
    "what medicine should i take",
    "should i start chemotherapy",
]

FIRST_PERSON_PATTERNS = [" i ", " my ", " me ", " ik ", " mijn "]


class SimpleMedicalRetriever:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.kanker_nl = LocalKankerNLDataset(settings)
        self.nkr = NKRCijfersClient(settings)
        self.kankeratlas = KankerAtlasClient(settings)

    def should_refuse(self, query: str) -> str | None:
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

    def retrieve(
        self,
        query: str,
        audience: Audience = "patient",
        limit: int | None = None,
    ) -> RetrievalResponse:
        refusal_reason = self.should_refuse(query)
        if refusal_reason:
            return RetrievalResponse(
                query=query,
                audience=audience,
                refusal_reason=refusal_reason,
                notes=["Unsafe prompt for an informational oncology assistant."],
            )

        routed_hits = self._route_structured_sources(query)
        if routed_hits:
            return RetrievalResponse(
                query=query,
                audience=audience,
                hits=routed_hits[: limit or self.settings.local_search_default_limit],
                notes=["Structured routing handled this query before local patient-content search."],
            )

        hits = self.kanker_nl.search(
            query=query,
            limit=limit or self.settings.local_search_default_limit,
        )
        notes = [
            "Local retrieval is currently backed by the bundled kanker.nl crawl.",
            "Structured NKR/Cancer Atlas routing should be layered on top for statistics and regional questions.",
        ]
        if not hits:
            notes.append("No local patient-content hit found; next step should be live API/crawl routing.")
        return RetrievalResponse(query=query, audience=audience, hits=hits, notes=notes)

    def _route_structured_sources(self, query: str) -> list[SearchHit]:
        query_lower = query.lower()

        if any(token in query_lower for token in ["nkr", "navigation topics", "stage distribution", "stadium"]):
            if "navigation" in query_lower:
                navigation = self.nkr.navigation_items()
                items = navigation.get("items", [])
                top_labels = []
                if items and isinstance(items[0], dict):
                    top_labels = [child["label"] for child in items[0].get("children", [])[:5]]
                text = "Available NKR topics: " + ", ".join(top_labels)
                return [
                    self._build_hit(
                        source_id="nkr-cijfers",
                        title="NKR Cijfers navigation",
                        url="https://nkr-cijfers.iknl.nl",
                        text=text,
                        excerpt=text,
                        score=1.0,
                    )
                ]

            stage_data = self.nkr.example_stage_distribution()
            excerpt = (
                "Structured NKR response fetched for incidence distribution per stadium "
                "for all cancers in 2024."
            )
            return [
                self._build_hit(
                    source_id="nkr-cijfers",
                    title="NKR Cijfers incidence distribution per stadium",
                    url="https://nkr-cijfers.iknl.nl/viewer/incidentie-verdeling-per-stadium",
                    text=str(stage_data)[:4000],
                    excerpt=excerpt,
                    score=1.0,
                )
            ]

        if any(token in query_lower for token in ["postcode", "regional", "region", "atlas", "lung cancer incidence"]):
            atlas = self.kankeratlas.cancer_data(11, 3, 3)
            rows = atlas.get("res", [])[:5]
            excerpt = "Top sample postcode rows from the lung-cancer atlas: " + ", ".join(
                f"{row['postcode']} (p50={row['p50']})"
                for row in rows
                if isinstance(row, dict) and "postcode" in row and "p50" in row
            )
            return [
                self._build_hit(
                    source_id="kankeratlas",
                    title="Cancer Atlas lung cancer incidence by postcode",
                    url="https://kankeratlas.iknl.nl",
                    text=str(rows),
                    excerpt=excerpt,
                    score=1.0,
                )
            ]

        if any(token in query_lower for token in ["guideline", "richtlijn", "prostate", "prostaat"]):
            text = "Example guideline entry for prostate carcinoma from Richtlijnendatabase."
            return [
                self._build_hit(
                    source_id="richtlijnendatabase",
                    title="Prostaatcarcinoom guideline overview",
                    url=(
                        "https://richtlijnendatabase.nl/richtlijn/prostaatcarcinoom/"
                        "prostaatcarcinoom_-_korte_beschrijving.html"
                    ),
                    text=text,
                    excerpt=text,
                    score=1.0,
                )
            ]

        return []

    def _build_hit(
        self,
        *,
        source_id: str,
        title: str,
        url: str,
        text: str,
        excerpt: str,
        score: float,
    ) -> SearchHit:
        provenance = Provenance(
            source_id=source_id,
            title=title,
            url=url,
            canonical_url=url,
            publisher="IKNL" if source_id != "richtlijnendatabase" else "Richtlijnendatabase",
            excerpt=excerpt,
        )
        document = SourceDocument(
            document_id=url,
            source_id=source_id,
            title=title,
            url=url,
            content_type="text/plain",
            text=text,
            provenance=provenance,
        )
        return SearchHit(score=score, excerpt=excerpt, document=document)
