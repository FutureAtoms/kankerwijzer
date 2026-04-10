-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Source catalog
CREATE TABLE IF NOT EXISTS source_catalog (
  source_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  publisher TEXT NOT NULL,
  trust_tier TEXT NOT NULL CHECK (trust_tier IN ('trusted')),
  access_mode TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Documents
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

-- Chunks with 1024-dim embeddings (multilingual-e5-large)
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

-- Ingestion runs
CREATE TABLE IF NOT EXISTS ingestion_runs (
  ingestion_run_id BIGSERIAL PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES source_catalog(source_id),
  status TEXT NOT NULL,
  details JSONB NOT NULL DEFAULT '{}'::jsonb,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at TIMESTAMPTZ
);

-- Evaluation runs
CREATE TABLE IF NOT EXISTS evaluation_runs (
  evaluation_run_id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  status TEXT NOT NULL,
  summary JSONB NOT NULL DEFAULT '{}'::jsonb,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at TIMESTAMPTZ
);

-- User feedback (enriched schema)
CREATE TABLE IF NOT EXISTS user_feedback (
  feedback_id BIGSERIAL PRIMARY KEY,
  query_text TEXT NOT NULL,
  answer_excerpt TEXT,
  citation_urls TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  is_helpful BOOLEAN,
  notes TEXT,
  feedback_type TEXT NOT NULL DEFAULT 'general',
  conversation_id TEXT,
  message_index INTEGER,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
