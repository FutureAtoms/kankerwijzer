"""Feedback system: collect and report on user feedback for KankerWijzer answers."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.config import get_settings

router = APIRouter(prefix="/feedback")
logger = logging.getLogger(__name__)

# In-memory store as fallback when Postgres is unavailable
_feedback_store: list[dict] = []


def _try_postgres_insert(record: dict) -> bool:
    """Try to insert a feedback record into Postgres. Returns True on success."""
    settings = get_settings()
    try:
        import psycopg

        with psycopg.connect(settings.postgres_url, autocommit=True) as conn:
            conn.execute(
                """
                INSERT INTO user_feedback (query_text, answer_excerpt, citation_urls, is_helpful, notes)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    record["query_text"],
                    record.get("answer_excerpt"),
                    record.get("citation_urls", []),
                    record.get("is_helpful"),
                    record.get("notes"),
                ),
            )
        return True
    except Exception:
        logger.debug("Postgres unavailable for feedback; using in-memory store", exc_info=True)
        return False


def _try_postgres_stats() -> dict | None:
    """Try to read feedback stats from Postgres. Returns None on failure."""
    settings = get_settings()
    try:
        import psycopg

        with psycopg.connect(settings.postgres_url) as conn:
            row = conn.execute("SELECT COUNT(*) FROM user_feedback").fetchone()
            total = row[0] if row else 0

            helpful_row = conn.execute(
                "SELECT COUNT(*) FROM user_feedback WHERE is_helpful = true"
            ).fetchone()
            helpful = helpful_row[0] if helpful_row else 0

            not_helpful_row = conn.execute(
                "SELECT COUNT(*) FROM user_feedback WHERE is_helpful = false"
            ).fetchone()
            not_helpful = not_helpful_row[0] if not_helpful_row else 0

            return {
                "total": total,
                "helpful": helpful,
                "not_helpful": not_helpful,
                "percent_helpful": round(helpful / total * 100, 1) if total > 0 else 0,
                "source": "postgres",
            }
    except Exception:
        return None


@router.post("/")
def submit_feedback(body: dict) -> dict:
    """Store feedback. Required: query_text, feedback_type.
    Optional: answer_excerpt, conversation_id, message_index, notes, citation_urls, is_helpful.
    """
    query_text = body.get("query_text")
    feedback_type = body.get("feedback_type")

    if not query_text or not feedback_type:
        raise HTTPException(
            status_code=422,
            detail="query_text and feedback_type are required",
        )

    valid_types = {"helpful", "missing_info", "incorrect", "unclear"}
    if feedback_type not in valid_types:
        raise HTTPException(
            status_code=422,
            detail=f"feedback_type must be one of: {', '.join(sorted(valid_types))}",
        )

    is_helpful = body.get("is_helpful")
    if is_helpful is None:
        is_helpful = feedback_type == "helpful"

    record = {
        "query_text": query_text,
        "feedback_type": feedback_type,
        "answer_excerpt": body.get("answer_excerpt"),
        "conversation_id": body.get("conversation_id"),
        "message_index": body.get("message_index"),
        "notes": body.get("notes"),
        "citation_urls": body.get("citation_urls", []),
        "is_helpful": is_helpful,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    stored_in_pg = _try_postgres_insert(record)
    if not stored_in_pg:
        _feedback_store.append(record)

    return {
        "status": "ok",
        "stored_in": "postgres" if stored_in_pg else "memory",
        "feedback_type": feedback_type,
    }


@router.get("/stats")
def feedback_stats() -> dict:
    """Return aggregate feedback stats."""
    pg_stats = _try_postgres_stats()
    if pg_stats is not None:
        return pg_stats

    # Fallback: in-memory stats
    total = len(_feedback_store)
    helpful = sum(1 for f in _feedback_store if f.get("is_helpful"))
    not_helpful = sum(1 for f in _feedback_store if f.get("is_helpful") is False)

    return {
        "total": total,
        "helpful": helpful,
        "not_helpful": not_helpful,
        "percent_helpful": round(helpful / total * 100, 1) if total > 0 else 0,
        "source": "memory",
    }
