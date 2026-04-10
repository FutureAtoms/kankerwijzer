from __future__ import annotations

from app.models import SourceDescriptor


SOURCE_REGISTRY: dict[str, SourceDescriptor] = {
    "kanker.nl": SourceDescriptor(
        source_id="kanker.nl",
        name="kanker.nl",
        description="Patient and caregiver cancer information",
        publisher="KWF / NFK / IKNL",
        trust_tier="trusted",
        access_mode="local_dataset",
        domains=["www.kanker.nl"],
        notes="Use bundled crawl first; live crawl only as fallback.",
    ),
    "iknl.nl": SourceDescriptor(
        source_id="iknl.nl",
        name="IKNL website",
        description="Professional and policy content from IKNL",
        publisher="IKNL",
        trust_tier="trusted",
        access_mode="crawl",
        domains=["iknl.nl", "www.iknl.nl"],
    ),
    "nkr-cijfers": SourceDescriptor(
        source_id="nkr-cijfers",
        name="NKR Cijfers",
        description="Registry-backed structured cancer statistics",
        publisher="IKNL",
        trust_tier="trusted",
        access_mode="api",
        domains=["nkr-cijfers.iknl.nl", "api.nkr-cijfers.iknl.nl"],
    ),
    "kankeratlas": SourceDescriptor(
        source_id="kankeratlas",
        name="Cancer Atlas",
        description="Regional incidence variation and postcode-based atlas data",
        publisher="IKNL",
        trust_tier="trusted",
        access_mode="api",
        domains=[
            "kankeratlas.iknl.nl",
            "iknl-atlas-strapi-prod.azurewebsites.net",
        ],
    ),
    "richtlijnendatabase": SourceDescriptor(
        source_id="richtlijnendatabase",
        name="Richtlijnendatabase",
        description="Dutch multidisciplinary oncology guidelines",
        publisher="Federatie Medisch Specialisten",
        trust_tier="trusted",
        access_mode="crawl",
        domains=["richtlijnendatabase.nl", "www.richtlijnendatabase.nl"],
        notes="Trusted source listed by IKNL, but maintained by Federatie Medisch Specialisten, not IKNL.",
    ),
    "iknl-reports": SourceDescriptor(
        source_id="iknl-reports",
        name="IKNL reports",
        description="Extensive analyses and big reports by IKNL",
        publisher="IKNL",
        trust_tier="trusted",
        access_mode="pdf",
        domains=["iknl.nl", "www.iknl.nl"],
        notes="3 bundled PDF reports in data/reports/.",
    ),
    "scientific-publications": SourceDescriptor(
        source_id="scientific-publications",
        name="IKNL scientific publications",
        description="Peer-reviewed scientific articles by IKNL researchers",
        publisher="IKNL",
        trust_tier="trusted",
        access_mode="pdf",
        domains=["iknl.nl", "www.iknl.nl"],
        notes="5 bundled PDFs in data/scientific_publications/. Not all may be open access.",
    ),
}


def list_approved_sources() -> list[SourceDescriptor]:
    return list(SOURCE_REGISTRY.values())
