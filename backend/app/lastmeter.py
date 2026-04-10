"""Lastmeter integration: stateless resource lookup for cancer patient distress domains."""

from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from app.connectors.kanker_nl import LocalKankerNLDataset

router = APIRouter(prefix="/lastmeter")

# ---- Domain structure for the frontend to render ----

LASTMETER_DOMAINS = [
    {
        "id": "physical",
        "name": "Lichamelijk",
        "icon": "\U0001f3e5",
        "items": [
            {"id": "pain", "label": "Pijn"},
            {"id": "fatigue", "label": "Vermoeidheid"},
            {"id": "sleep", "label": "Slaapproblemen"},
            {"id": "nausea", "label": "Misselijkheid"},
            {"id": "appetite", "label": "Eetproblemen"},
            {"id": "breathing", "label": "Benauwdheid"},
            {"id": "mobility", "label": "Bewegen"},
            {"id": "appearance", "label": "Uiterlijke veranderingen"},
        ],
    },
    {
        "id": "emotional",
        "name": "Emotioneel",
        "icon": "\U0001f4ad",
        "items": [
            {"id": "anxiety", "label": "Angst"},
            {"id": "depression", "label": "Somberheid"},
            {"id": "worry", "label": "Zorgen"},
            {"id": "anger", "label": "Boosheid"},
            {"id": "loss_of_interest", "label": "Verlies van interesse"},
        ],
    },
    {
        "id": "practical",
        "name": "Praktisch",
        "icon": "\U0001f4cb",
        "items": [
            {"id": "work", "label": "Werk"},
            {"id": "financial", "label": "Financi\u00ebn / Verzekering"},
            {"id": "childcare", "label": "Kinderopvang"},
            {"id": "transport", "label": "Vervoer"},
        ],
    },
    {
        "id": "social",
        "name": "Sociaal",
        "icon": "\U0001f465",
        "items": [
            {"id": "partner", "label": "Partner / Relatie"},
            {"id": "family", "label": "Familie"},
            {"id": "friends", "label": "Vrienden"},
            {"id": "children", "label": "Kinderen"},
        ],
    },
    {
        "id": "spiritual",
        "name": "Zingeving",
        "icon": "\U0001f31f",
        "items": [
            {"id": "meaning", "label": "Zingeving"},
            {"id": "faith", "label": "Geloof"},
            {"id": "death", "label": "Angst voor overlijden"},
        ],
    },
]

# ---- Mapping from domain keywords to kanker.nl search queries ----

DOMAIN_RESOURCES: dict[str, list[str]] = {
    "physical:pain": ["pijn bij kanker", "pijnbestrijding"],
    "physical:fatigue": ["vermoeidheid bij kanker", "vermoeidheid"],
    "physical:sleep": ["slaapproblemen kanker"],
    "physical:nausea": ["misselijkheid bij kanker"],
    "physical:appetite": ["eetproblemen kanker", "gewichtsverlies"],
    "physical:breathing": ["benauwdheid kanker"],
    "physical:mobility": ["bewegen bij kanker"],
    "physical:appearance": ["uiterlijke veranderingen kanker"],
    "emotional:anxiety": ["angst bij kanker", "angst en kanker"],
    "emotional:depression": ["somberheid kanker", "depressie bij kanker"],
    "emotional:worry": ["zorgen bij kanker", "onzekerheid kanker"],
    "emotional:anger": ["boosheid kanker", "frustratie kanker"],
    "emotional:loss_of_interest": ["geen interesse meer", "verlies interesse"],
    "practical:work": ["werk en kanker", "werken met kanker"],
    "practical:financial": ["financiele gevolgen kanker", "verzekering kanker"],
    "practical:childcare": ["kinderen en kanker"],
    "practical:transport": ["vervoer naar ziekenhuis"],
    "social:partner": ["relatie en kanker", "partner kanker"],
    "social:family": ["familie en kanker"],
    "social:friends": ["vrienden en kanker"],
    "social:children": ["kinderen en kanker", "praten over kanker"],
    "spiritual:meaning": ["zingeving kanker", "waarom ik"],
    "spiritual:faith": ["geloof en kanker"],
    "spiritual:death": ["angst voor overlijden", "levenseinde"],
}

# Lazy-loaded dataset reference
_dataset: LocalKankerNLDataset | None = None


def _get_dataset() -> LocalKankerNLDataset:
    global _dataset
    if _dataset is None:
        _dataset = LocalKankerNLDataset(get_settings())
    return _dataset


@router.get("/domains")
def get_domains() -> list[dict]:
    """Return available Lastmeter domains and items for the frontend."""
    return LASTMETER_DOMAINS


@router.post("/resources")
def get_resources(body: dict) -> list[dict]:
    """Receives domain keywords, returns kanker.nl resource URLs. NO scores stored."""
    domains = body.get("domains", [])
    dataset = _get_dataset()
    resources: list[dict] = []
    seen_urls: set[str] = set()

    for domain_key in domains:
        search_queries = DOMAIN_RESOURCES.get(domain_key, [])
        for sq in search_queries:
            try:
                hits = dataset.search(sq, limit=3)
            except Exception:
                continue
            for hit in hits:
                url = hit.document.url
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                resources.append(
                    {
                        "domain": domain_key,
                        "title": hit.document.title,
                        "url": url,
                        "excerpt": hit.excerpt[:200] if hit.excerpt else "",
                    }
                )

    return resources
