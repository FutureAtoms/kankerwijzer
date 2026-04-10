"""Qdrant client wrapper for the KankerWijzer vector index."""

from __future__ import annotations

import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.config import get_settings


class QdrantStore:
    """Thin wrapper around qdrant-client for upsert and search."""

    def __init__(self, url: str | None = None, collection: str | None = None):
        settings = get_settings()
        self.url = url or settings.qdrant_url
        self.collection = collection or settings.qdrant_collection
        self.client = QdrantClient(url=self.url)

    # ------------------------------------------------------------------
    # Collection management
    # ------------------------------------------------------------------

    def create_collection(self, dim: int | None = None) -> None:
        """Create the collection if it does not already exist."""
        dim = dim or get_settings().embedding_dim
        collections = [c.name for c in self.client.get_collections().collections]
        if self.collection in collections:
            return
        self.client.create_collection(
            collection_name=self.collection,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )

    # ------------------------------------------------------------------
    # Upsert
    # ------------------------------------------------------------------

    def upsert_batch(
        self,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict[str, Any]],
        batch_size: int = 100,
    ) -> int:
        """Upsert points in batches. Returns total upserted count."""
        total = 0
        for start in range(0, len(ids), batch_size):
            end = start + batch_size
            batch_ids = ids[start:end]
            batch_vectors = vectors[start:end]
            batch_payloads = payloads[start:end]

            points = [
                PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_URL, cid)),
                    vector=vec,
                    payload=pay,
                )
                for cid, vec, pay in zip(batch_ids, batch_vectors, batch_payloads)
            ]
            self.client.upsert(collection_name=self.collection, points=points)
            total += len(points)
        return total

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        source_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search and return results with full provenance payload.

        Returns list of dicts with keys:
            chunk_id, document_id, source_id, citation_url, canonical_url,
            title, page_number, section, text, score
        """
        query_filter = None
        if source_filter:
            query_filter = Filter(
                must=[
                    FieldCondition(key="source_id", match=MatchValue(value=source_filter))
                ]
            )

        hits = self.client.query_points(
            collection_name=self.collection,
            query=query_vector,
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
        ).points

        results: list[dict[str, Any]] = []
        for hit in hits:
            payload = hit.payload or {}
            results.append(
                {
                    "chunk_id": payload.get("chunk_id"),
                    "document_id": payload.get("document_id"),
                    "source_id": payload.get("source_id"),
                    "citation_url": payload.get("citation_url"),
                    "canonical_url": payload.get("canonical_url"),
                    "title": payload.get("title"),
                    "page_number": payload.get("page_number"),
                    "section": payload.get("section"),
                    "text": payload.get("text"),
                    "score": hit.score,
                }
            )
        return results
