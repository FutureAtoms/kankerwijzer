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
    # Treatment decisions
    (r"moet\s*ik\s*(stoppen|starten|nemen|beginnen|veranderen|wisselen|overstappen)", "treatment_decision"),
    (r"wel\s*of\s*niet\s*(behandel|operatie|chemo|bestraling)", "treatment_decision"),
    # Diagnosis seeking
    (r"heb\s*ik\s*kanker", "diagnosis"),
    (r"diagnose\s*(me|mij|stellen)", "diagnosis"),
    (r"(is\s*dit|wat\s*heb\s*ik|wat\s*mankeert)", "diagnosis"),
]

ROUTING_MESSAGES: dict[str, str] = {
    "emergency": "Bij acute nood: bel 112. Buiten kantooruren: bel de huisartsenpost.",
    "crisis": "Bij suicidale gedachten: bel 113 Zelfmoordpreventie (0900-0113) of chat via 113.nl.",
    "treatment_decision": "Bespreek behandelbeslissingen altijd met uw behandelend arts of specialist.",
    "diagnosis": "Neem contact op met uw huisarts voor onderzoek en diagnose.",
}


def check_red_flags(query: str) -> tuple[str | None, str | None]:
    """Return (flag_type, routing_message) if red flags detected, else (None, None)."""
    query_lower = query.lower()
    for pattern, flag_type in RED_FLAG_PATTERNS:
        if re.search(pattern, query_lower):
            return flag_type, ROUTING_MESSAGES[flag_type]
    return None, None
