"""Write ingested sources, documents and chunks to PostgreSQL."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

import psycopg
from psycopg.rows import dict_row


@dataclass
class ChunkRow:
    chunk_id: str
    document_id: str
    chunk_index: int
    chunk_text: str
    citation_url: str
    page_number: int | None = None
    section: str | None = None


@dataclass
class DocumentRow:
    document_id: str
    source_id: str
    canonical_url: str
    title: str
    content_type: str
    language: str = "nl"
    checksum: str | None = None


@dataclass
class SourceRow:
    source_id: str
    name: str
    publisher: str
    trust_tier: str = "trusted"
    access_mode: str = "local_dataset"


def make_chunk_id(document_id: str, chunk_index: int) -> str:
    """Compute chunk_id as SHA256(document_id + ':' + str(chunk_index))[:16]."""
    raw = f"{document_id}:{chunk_index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class PostgresWriter:
    """Batch writer for the KankerWijzer ingestion pipeline."""

    def __init__(self, postgres_url: str) -> None:
        self.postgres_url = postgres_url

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.postgres_url, row_factory=dict_row)

    def ensure_schema(self) -> None:
        """Create tables if they don't exist (idempotent)."""
        ddl = """
        CREATE EXTENSION IF NOT EXISTS vector;

        CREATE TABLE IF NOT EXISTS source_catalog (
          source_id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          publisher TEXT NOT NULL,
          trust_tier TEXT NOT NULL CHECK (trust_tier IN ('trusted')),
          access_mode TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS documents (
          document_id TEXT PRIMARY KEY,
          source_id TEXT NOT NULL REFERENCES source_catalog(source_id),
          canonical_url TEXT NOT NULL,
          title TEXT NOT NULL,
          content_type TEXT NOT NULL,
          language TEXT NOT NULL DEFAULT 'nl',
          checksum TEXT,
          version_tag TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS chunks (
          chunk_id TEXT PRIMARY KEY,
          document_id TEXT NOT NULL REFERENCES documents(document_id),
          chunk_index INTEGER NOT NULL,
          chunk_text TEXT NOT NULL,
          page_number INTEGER,
          section TEXT,
          citation_url TEXT NOT NULL,
          start_offset INTEGER,
          end_offset INTEGER,
          embedding VECTOR(1024)
        );

        CREATE INDEX IF NOT EXISTS chunks_document_idx ON chunks(document_id);
        CREATE INDEX IF NOT EXISTS chunks_page_idx ON chunks(page_number);

        CREATE TABLE IF NOT EXISTS ingestion_runs (
          ingestion_run_id BIGSERIAL PRIMARY KEY,
          source_id TEXT NOT NULL REFERENCES source_catalog(source_id),
          status TEXT NOT NULL,
          details JSONB NOT NULL DEFAULT '{}'::jsonb,
          started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          finished_at TIMESTAMPTZ
        );
        """
        with self._connect() as conn:
            conn.execute(ddl)
            conn.commit()

    def upsert_source(self, source: SourceRow) -> None:
        sql = """
        INSERT INTO source_catalog (source_id, name, publisher, trust_tier, access_mode)
        VALUES (%(source_id)s, %(name)s, %(publisher)s, %(trust_tier)s, %(access_mode)s)
        ON CONFLICT (source_id) DO NOTHING
        """
        with self._connect() as conn:
            conn.execute(sql, {
                "source_id": source.source_id,
                "name": source.name,
                "publisher": source.publisher,
                "trust_tier": source.trust_tier,
                "access_mode": source.access_mode,
            })
            conn.commit()

    def upsert_documents(self, docs: list[DocumentRow]) -> int:
        """Insert documents, skip on conflict. Returns number inserted."""
        if not docs:
            return 0
        sql = """
        INSERT INTO documents (document_id, source_id, canonical_url, title, content_type, language, checksum)
        VALUES (%(document_id)s, %(source_id)s, %(canonical_url)s, %(title)s, %(content_type)s, %(language)s, %(checksum)s)
        ON CONFLICT (document_id) DO UPDATE SET
            checksum = EXCLUDED.checksum,
            updated_at = NOW()
        """
        count = 0
        with self._connect() as conn:
            for doc in docs:
                conn.execute(sql, {
                    "document_id": doc.document_id,
                    "source_id": doc.source_id,
                    "canonical_url": doc.canonical_url,
                    "title": doc.title,
                    "content_type": doc.content_type,
                    "language": doc.language,
                    "checksum": doc.checksum,
                })
                count += 1
            conn.commit()
        return count

    def upsert_chunks(self, chunks: list[ChunkRow]) -> int:
        """Insert chunks, skip on conflict. Returns number inserted."""
        if not chunks:
            return 0
        sql = """
        INSERT INTO chunks (chunk_id, document_id, chunk_index, chunk_text, page_number, section, citation_url)
        VALUES (%(chunk_id)s, %(document_id)s, %(chunk_index)s, %(chunk_text)s, %(page_number)s, %(section)s, %(citation_url)s)
        ON CONFLICT (chunk_id) DO NOTHING
        """
        count = 0
        with self._connect() as conn:
            with conn.cursor() as cur:
                for chunk in chunks:
                    cur.execute(sql, {
                        "chunk_id": chunk.chunk_id,
                        "document_id": chunk.document_id,
                        "chunk_index": chunk.chunk_index,
                        "chunk_text": chunk.chunk_text,
                        "page_number": chunk.page_number,
                        "section": chunk.section,
                        "citation_url": chunk.citation_url,
                    })
                    count += 1
            conn.commit()
        return count

    def delete_chunks_for_document(self, document_id: str) -> int:
        """Delete all chunks for a document (useful for re-ingestion)."""
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM chunks WHERE document_id = %s", (document_id,)
            )
            conn.commit()
            return cur.rowcount

    def get_counts(self) -> dict[str, int]:
        """Return counts of sources, documents, chunks."""
        with self._connect() as conn:
            sources = conn.execute("SELECT count(*) as cnt FROM source_catalog").fetchone()
            docs = conn.execute("SELECT count(*) as cnt FROM documents").fetchone()
            chunks = conn.execute("SELECT count(*) as cnt FROM chunks").fetchone()
            return {
                "sources": sources["cnt"] if sources else 0,
                "documents": docs["cnt"] if docs else 0,
                "chunks": chunks["cnt"] if chunks else 0,
            }
