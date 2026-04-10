"""Paragraph-aware text chunking for the KankerWijzer ingestion pipeline."""

from __future__ import annotations

MAX_CHUNK_CHARS = 2048  # ~512 tokens at 4 chars/token
OVERLAP_CHARS = 256  # ~64 tokens overlap


def chunk_text(text: str) -> list[str]:
    """Split *text* into chunks respecting paragraph boundaries.

    Strategy:
    1. Split on double-newlines (paragraph boundaries).
    2. Accumulate paragraphs until the next one would exceed MAX_CHUNK_CHARS.
    3. Emit the chunk, then start a new chunk with OVERLAP_CHARS of trailing
       context from the previous chunk.
    4. Any single paragraph longer than MAX_CHUNK_CHARS is hard-split by
       character with overlap.

    Returns a list of non-empty chunk strings.
    """
    if not text or not text.strip():
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    if not paragraphs:
        return []

    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        # If the paragraph alone exceeds max, hard-split it
        if len(para) > MAX_CHUNK_CHARS:
            # First, flush current buffer
            if current:
                chunks.append(current.strip())
                overlap_text = current[-OVERLAP_CHARS:] if len(current) > OVERLAP_CHARS else current
                current = overlap_text.strip()
            # Hard-split the long paragraph
            start = 0
            while start < len(para):
                end = start + MAX_CHUNK_CHARS
                piece = para[start:end]
                if current:
                    combined = current + "\n\n" + piece
                    if len(combined) <= MAX_CHUNK_CHARS:
                        chunks.append(combined.strip())
                    else:
                        chunks.append(current.strip())
                        chunks.append(piece.strip())
                    current = ""
                else:
                    chunks.append(piece.strip())
                overlap_start = max(0, end - OVERLAP_CHARS)
                current = para[overlap_start:end].strip()
                start = end
            continue

        candidate = (current + "\n\n" + para).strip() if current else para
        if len(candidate) <= MAX_CHUNK_CHARS:
            current = candidate
        else:
            # Emit current, start new with overlap
            if current:
                chunks.append(current.strip())
                overlap_text = current[-OVERLAP_CHARS:] if len(current) > OVERLAP_CHARS else current
                current = (overlap_text.strip() + "\n\n" + para).strip()
                # If even overlap + para exceeds max, just use para
                if len(current) > MAX_CHUNK_CHARS:
                    current = para
            else:
                current = para

    # Flush remaining
    if current and current.strip():
        chunks.append(current.strip())

    # Deduplicate consecutive identical chunks (can happen with overlap logic)
    deduped: list[str] = []
    for c in chunks:
        if not deduped or c != deduped[-1]:
            deduped.append(c)

    return deduped
