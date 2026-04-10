from __future__ import annotations

from app.config import Settings
from app.models import AnswerResponse, Provenance
from app.retrieval.simple import SimpleMedicalRetriever


class AnthropicUnavailableError(RuntimeError):
    pass


class MedicalAnswerOrchestrator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.retriever = SimpleMedicalRetriever(settings)

    def _client(self):
        if not self.settings.anthropic_api_key:
            raise AnthropicUnavailableError("ANTHROPIC_API_KEY is not configured.")
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise AnthropicUnavailableError(
                "Anthropic SDK not installed. Run `uv sync --extra anthropic`."
            ) from exc
        return Anthropic(api_key=self.settings.anthropic_api_key)

    def answer(self, query: str, audience: str = "patient", limit: int = 5) -> AnswerResponse:
        retrieval = self.retriever.retrieve(query=query, audience=audience, limit=limit)
        if retrieval.refusal_reason:
            return AnswerResponse(
                query=query,
                audience=audience,
                refusal_reason=retrieval.refusal_reason,
                notes=retrieval.notes,
            )

        citations: list[Provenance] = [hit.document.provenance for hit in retrieval.hits]
        evidence_lines = []
        for idx, hit in enumerate(retrieval.hits, start=1):
            evidence_lines.append(
                f"[SRC-{idx}] {hit.document.title}\n"
                f"URL: {hit.document.url}\n"
                f"Excerpt: {hit.excerpt}\n"
            )

        try:
            client = self._client()
        except AnthropicUnavailableError as exc:
            notes = retrieval.notes + [str(exc)]
            return AnswerResponse(
                query=query,
                audience=audience,
                answer_markdown=None,
                citations=citations,
                notes=notes,
            )

        prompt = (
            "You are an oncology information assistant.\n"
            "Rules:\n"
            "1. Use only the evidence blocks.\n"
            "2. If the evidence is insufficient, say so.\n"
            "3. Do not provide personalized diagnosis or treatment instructions.\n"
            "4. Cite every factual claim with one or more labels like [SRC-1].\n\n"
            f"Audience: {audience}\n"
            f"Question: {query}\n\n"
            "Evidence:\n"
            + "\n".join(evidence_lines)
        )
        response = client.messages.create(
            model=self.settings.anthropic_model,
            max_tokens=1200,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        text_blocks = [block.text for block in response.content if getattr(block, "type", None) == "text"]
        answer_markdown = "\n".join(text_blocks).strip() if text_blocks else None
        return AnswerResponse(
            query=query,
            audience=audience,
            answer_markdown=answer_markdown,
            citations=citations,
            notes=retrieval.notes,
        )
