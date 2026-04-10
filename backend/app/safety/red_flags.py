"""Red-flag symptom routing -- detect urgent/emergency language."""

from __future__ import annotations

import re

RED_FLAG_PATTERNS: list[tuple[str, str]] = [
    # Emergency symptoms
    (r"bloed\s*(braken|spugen|ophoesten)", "emergency"),
    (r"(braak|spuug|hoest)\s*(bloed|op\s*bloed)", "emergency"),
    (r"bewusteloos", "emergency"),
    (r"ernstige\s*(pijn|bloeding)", "emergency"),
    (r"(hartaanval|beroerte|hartinfarct)", "emergency"),
    # Suicidal / crisis
    (r"suicid|zelfmoord|zelfdoding|zelfbeschadiging", "crisis"),
    (r"wil\s*(niet\s*meer|dood|einde)", "crisis"),
    (r"(kan\s*niet\s*meer|geen\s*zin\s*meer|wanhopig)", "crisis"),
    # Treatment decisions
    (r"moet\s*ik\s*(stoppen|starten|nemen|beginnen|veranderen|wisselen|overstappen)", "treatment_decision"),
    (r"wel\s*of\s*niet\s*(behandel|operatie|chemo|bestraling)", "treatment_decision"),
    # Diagnosis seeking
    (r"heb\s*ik\s*kanker", "diagnosis"),
    (r"diagnose\s*(me|mij|stellen)", "diagnosis"),
    (r"(is\s*dit|wat\s*heb\s*ik|wat\s*mankeert)", "diagnosis"),
]

# Structured routing with contact information
ROUTING_INFO: dict[str, dict] = {
    "emergency": {
        "message": "Bij acute nood: bel onmiddellijk 112 of ga naar de dichtstbijzijnde spoedeisende hulp.",
        "severity": "critical",
        "contacts": [
            {
                "name": "Alarmnummer",
                "phone": "112",
                "description": "Voor levensbedreigende situaties",
                "icon": "emergency",
            },
            {
                "name": "Huisartsenpost",
                "phone": "0900-1515",
                "description": "Buiten kantooruren van uw huisarts",
                "icon": "medical",
            },
        ],
    },
    "crisis": {
        "message": "U staat er niet alleen voor. Neem alstublieft contact op met een van deze hulplijnen.",
        "severity": "urgent",
        "contacts": [
            {
                "name": "113 Zelfmoordpreventie",
                "phone": "0900-0113",
                "url": "https://www.113.nl",
                "description": "24/7 bereikbaar — bellen, chatten of mailen",
                "icon": "crisis",
            },
            {
                "name": "KWF Kanker Infolijn",
                "phone": "0800-0226622",
                "email": "info@kwf.nl",
                "description": "Gratis, ma-vr 9:00-17:00 — voor vragen en emotionele steun",
                "icon": "support",
            },
            {
                "name": "IPSO (psycho-oncologie)",
                "phone": "030-2916090",
                "url": "https://www.ipso.nl",
                "description": "Professionele psychologische hulp bij kanker",
                "icon": "support",
            },
        ],
    },
    "treatment_decision": {
        "message": "Behandelbeslissingen zijn persoonlijk en complex. Bespreek dit met uw behandelteam.",
        "severity": "info",
        "contacts": [
            {
                "name": "Uw behandelend arts",
                "description": "Neem contact op met uw specialist of oncologisch verpleegkundige",
                "icon": "medical",
            },
            {
                "name": "KWF Kanker Infolijn",
                "phone": "0800-0226622",
                "email": "info@kwf.nl",
                "description": "Gratis informatie en ondersteuning, ma-vr 9:00-17:00",
                "icon": "support",
            },
        ],
    },
    "diagnosis": {
        "message": "Voor een diagnose is medisch onderzoek nodig. Neem contact op met uw huisarts.",
        "severity": "info",
        "contacts": [
            {
                "name": "Uw huisarts",
                "description": "Maak een afspraak voor onderzoek en verwijzing",
                "icon": "medical",
            },
            {
                "name": "KWF Kanker Infolijn",
                "phone": "0800-0226622",
                "email": "info@kwf.nl",
                "description": "Gratis informatie over onderzoeken en diagnose",
                "icon": "support",
            },
        ],
    },
}

# Plain-text fallback for backward compatibility
ROUTING_MESSAGES: dict[str, str] = {
    key: info["message"] for key, info in ROUTING_INFO.items()
}


def check_red_flags(query: str) -> tuple[str | None, str | None]:
    """Return (flag_type, routing_message) if red flags detected, else (None, None)."""
    query_lower = query.lower()
    for pattern, flag_type in RED_FLAG_PATTERNS:
        if re.search(pattern, query_lower):
            return flag_type, ROUTING_MESSAGES[flag_type]
    return None, None


def get_routing_info(flag_type: str) -> dict | None:
    """Return full routing info with contacts for a flag type."""
    return ROUTING_INFO.get(flag_type)
