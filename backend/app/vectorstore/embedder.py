"""Embedding wrapper for multilingual-e5-large (1024-dim)."""

from __future__ import annotations

from app.config import get_settings


class Embedder:
    """Wraps sentence-transformers for passage / query embedding with E5 prefixes."""

    def __init__(self, model_name: str | None = None):
        from sentence_transformers import SentenceTransformer

        model_name = model_name or get_settings().embedding_model
        self.model = SentenceTransformer(model_name)

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        """Embed passages with 'passage: ' prefix (E5 convention)."""
        prefixed = [f"passage: {t}" for t in texts]
        return self.model.encode(prefixed, show_progress_bar=True, batch_size=64).tolist()

    def embed_query(self, query: str) -> list[float]:
        """Embed a single query with 'query: ' prefix (E5 convention)."""
        return self.model.encode(f"query: {query}").tolist()
