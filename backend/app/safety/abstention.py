"""Evidence-threshold abstention for medical-grade retrieval."""

from __future__ import annotations

from app.models import SearchHit


def check_evidence_threshold(hits: list[SearchHit], threshold: float) -> str | None:
    """Return refusal_reason if all hits are below threshold, else None."""
    if not hits:
        return "insufficient_evidence"
    top_score = max(h.score for h in hits)
    if top_score < threshold:
        return "insufficient_evidence"
    return None
