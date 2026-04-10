from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


Audience = Literal["patient", "professional", "policy"]


class SourceDescriptor(BaseModel):
    source_id: str
    name: str
    description: str
    publisher: str
    trust_tier: Literal["trusted"]
    access_mode: Literal["api", "local_dataset", "crawl", "pdf"]
    domains: list[str] = Field(default_factory=list)
    notes: str | None = None


class Provenance(BaseModel):
    source_id: str
    title: str
    url: str
    canonical_url: str | None = None
    document_id: str | None = None
    chunk_id: str | None = None
    publisher: str | None = None
    page_number: int | None = None
    section: str | None = None
    excerpt: str | None = None
    checksum: str | None = None
    fetched_at: datetime | None = None
    relevance_score: float | None = Field(None, description="Retrieval relevance score 0.0-1.0 for this source")
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceDocument(BaseModel):
    document_id: str
    source_id: str
    title: str
    url: str
    content_type: str
    language: str = "nl"
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    provenance: Provenance


class SearchHit(BaseModel):
    score: float
    excerpt: str
    document: SourceDocument


class RetrievalResponse(BaseModel):
    query: str
    audience: Audience
    hits: list[SearchHit] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    refusal_reason: str | None = None


class AnswerResponse(BaseModel):
    query: str
    audience: Audience
    answer_markdown: str | None = None
    citations: list[Provenance] = Field(default_factory=list)
    confidence: float | None = Field(None, description="Overall answer confidence 0.0-1.0")
    confidence_label: str | None = Field(None, description="Human-readable confidence: hoog/gemiddeld/laag")
    notes: list[str] = Field(default_factory=list)
    refusal_reason: str | None = None


class FirecrawlRequest(BaseModel):
    url: str
    formats: list[str] = Field(default_factory=lambda: ["markdown"])
    limit: int = 25
    include_paths: list[str] = Field(default_factory=list)
    exclude_paths: list[str] = Field(default_factory=list)


class ParsePdfRequest(BaseModel):
    path: str


class QuestionRequest(BaseModel):
    query: str
    audience: Audience = "patient"
    limit: int = 5
