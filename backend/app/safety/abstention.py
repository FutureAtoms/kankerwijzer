"""Evidence-threshold abstention for medical-grade retrieval."""

from __future__ import annotations

import re

from app.models import SearchHit


_SPECIFIC_CANCER_TERM_RE = re.compile(r"\b([a-zà-ÿ0-9-]*kanker)\b", re.IGNORECASE)


def extract_specific_cancer_terms(query: str) -> list[str]:
    """Return specific cancer terms mentioned in the query.

    Generic "kanker" by itself is not enough to trigger low-coverage refusal.
    """
    terms: list[str] = []
    for match in _SPECIFIC_CANCER_TERM_RE.findall(query.lower()):
        normalized = match.strip("- ")
        if normalized == "kanker":
            continue
        if normalized not in terms:
            terms.append(normalized)
    return terms


def check_evidence_threshold(hits: list[SearchHit], threshold: float) -> str | None:
    """Return refusal_reason if all hits are below threshold, else None."""
    if not hits:
        return "insufficient_evidence"
    top_score = max(h.score for h in hits)
    if top_score < threshold:
        return "insufficient_evidence"
    return None


def check_low_coverage(query: str, hits: list[SearchHit]) -> str | None:
    """Refuse when a specific cancer term is missing from the retrieved evidence."""
    requested_terms = extract_specific_cancer_terms(query)
    if not requested_terms or not hits:
        return None

    corpus = "\n".join(
        " ".join(
            part
            for part in (
                hit.document.title,
                hit.document.text[:1200],
                hit.excerpt,
            )
            if part
        ).lower()
        for hit in hits
    )

    if any(term in corpus for term in requested_terms):
        return None
    return "low_coverage_specific_cancer"
