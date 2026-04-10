"""
Index all Postgres chunks into Qdrant and write embeddings back to Postgres.

Usage:
    uv run python -m app.vectorstore.indexer
"""

from __future__ import annotations

import hashlib
import sys
import time

import psycopg

from app.config import get_settings
from app.vectorstore.embedder import Embedder
from app.vectorstore.qdrant_store import QdrantStore


def _checksum(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def main() -> None:
    settings = get_settings()
    print(f"[indexer] connecting to Postgres: {settings.postgres_url.split('@')[1]}")
    print(f"[indexer] Qdrant target: {settings.qdrant_url} / {settings.qdrant_collection}")

    # ------------------------------------------------------------------
    # 1. Read chunks + document metadata from Postgres
    # ------------------------------------------------------------------
    print("[indexer] reading chunks from Postgres ...")
    with psycopg.connect(settings.postgres_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.chunk_id,
                       c.chunk_text,
                       c.document_id,
                       c.citation_url,
                       c.page_number,
                       c.section,
                       d.source_id,
                       d.canonical_url,
                       d.title,
                       d.checksum
                  FROM chunks c
                  JOIN documents d ON c.document_id = d.document_id
                 ORDER BY c.chunk_id
                """
            )
            rows = cur.fetchall()

    if not rows:
        print("[indexer] no chunks found in Postgres -- nothing to do")
        sys.exit(0)

    print(f"[indexer] loaded {len(rows)} chunks")

    chunk_ids: list[str] = []
    texts: list[str] = []
    payloads: list[dict] = []

    for row in rows:
        (
            chunk_id,
            chunk_text,
            document_id,
            citation_url,
            page_number,
            section,
            source_id,
            canonical_url,
            title,
            doc_checksum,
        ) = row
        chunk_ids.append(chunk_id)
        texts.append(chunk_text)
        payloads.append(
            {
                "chunk_id": chunk_id,
                "document_id": document_id,
                "source_id": source_id,
                "citation_url": citation_url,
                "canonical_url": canonical_url,
                "title": title,
                "page_number": page_number,
                "section": section,
                "text": chunk_text,
                "checksum": _checksum(chunk_text),
            }
        )

    # ------------------------------------------------------------------
    # 2. Embed all chunk texts
    # ------------------------------------------------------------------
    print(f"[indexer] embedding {len(texts)} chunks (model={settings.embedding_model}) ...")
    t0 = time.time()
    embedder = Embedder()
    vectors = embedder.embed_passages(texts)
    elapsed = time.time() - t0
    print(f"[indexer] embedding done in {elapsed:.1f}s ({len(vectors)} vectors, dim={len(vectors[0])})")

    # ------------------------------------------------------------------
    # 3. Upsert to Qdrant
    # ------------------------------------------------------------------
    print("[indexer] upserting to Qdrant ...")
    store = QdrantStore()
    store.create_collection()
    t0 = time.time()
    n = store.upsert_batch(chunk_ids, vectors, payloads)
    elapsed = time.time() - t0
    print(f"[indexer] upserted {n} points in {elapsed:.1f}s")

    # ------------------------------------------------------------------
    # 4. Write embeddings back to Postgres (chunks.embedding column)
    # ------------------------------------------------------------------
    print("[indexer] writing embeddings back to Postgres ...")
    t0 = time.time()
    with psycopg.connect(settings.postgres_url) as conn:
        with conn.cursor() as cur:
            # Batch update using executemany for efficiency
            batch_size = 500
            for start in range(0, len(chunk_ids), batch_size):
                end = start + batch_size
                batch = [
                    (str(vec), cid)
                    for cid, vec in zip(chunk_ids[start:end], vectors[start:end])
                ]
                cur.executemany(
                    "UPDATE chunks SET embedding = %s::vector WHERE chunk_id = %s",
                    batch,
                )
            conn.commit()
    elapsed = time.time() - t0
    print(f"[indexer] wrote {len(chunk_ids)} embeddings to Postgres in {elapsed:.1f}s")

    # ------------------------------------------------------------------
    # 5. Verify
    # ------------------------------------------------------------------
    info = store.client.get_collection(settings.qdrant_collection)
    print(f"[indexer] Qdrant collection '{settings.qdrant_collection}' points_count={info.points_count}")
    print("[indexer] done.")


if __name__ == "__main__":
    main()
