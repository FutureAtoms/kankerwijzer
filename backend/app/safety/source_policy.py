"""Source whitelist enforcement for approved medical information sources."""

from __future__ import annotations

APPROVED_SOURCES: set[str] = {
    "kanker.nl",
    "iknl.nl",
    "nkr-cijfers",
    "kankeratlas",
    "richtlijnendatabase",
    "iknl-reports",
    "scientific-publications",
}


def validate_source(source_id: str) -> bool:
    """Return True if source_id is approved."""
    return source_id in APPROVED_SOURCES


def get_publisher_note(source_id: str) -> str | None:
    """Return disclaimer note for sources not maintained by IKNL."""
    if source_id == "richtlijnendatabase":
        return "Deze richtlijn is opgesteld door de Federatie Medisch Specialisten, niet door IKNL."
    return None
