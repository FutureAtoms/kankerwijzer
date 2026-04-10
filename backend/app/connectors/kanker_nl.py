from __future__ import annotations

import json
import re
from functools import cached_property

import httpx

from app.config import Settings
from app.models import Provenance, SearchHit, SourceDocument


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-ZÀ-ÿ0-9]+", text.lower())


def _excerpt(text: str, query: str, size: int = 240) -> str:
    lower = text.lower()
    query_lower = query.lower()
    idx = lower.find(query_lower)
    if idx < 0:
        return text[:size].replace("\n", " ")
    start = max(0, idx - size // 3)
    end = min(len(text), idx + size)
    return text[start:end].replace("\n", " ").strip()


class LocalKankerNLDataset:
    SAMPLE_URL = "https://www.kanker.nl/kankersoorten/borstkanker/algemeen/wat-is-borstkanker"
    ROBOTS_URL = "https://www.kanker.nl/robots.txt"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @cached_property
    def pages(self) -> dict[str, dict[str, str]]:
        return json.loads(self.settings.kanker_dataset_path.read_text(encoding="utf-8"))

    def search(self, query: str, limit: int = 5, cancer_type: str | None = None) -> list[SearchHit]:
        query_tokens = set(_tokenize(query))
        hits: list[SearchHit] = []

        for url, payload in self.pages.items():
            if cancer_type and payload.get("kankersoort") != cancer_type:
                continue

            text = payload.get("text", "")
            title = text.splitlines()[0].strip() if text else url.rsplit("/", 1)[-1]
            body_tokens = _tokenize(text)
            overlap = query_tokens.intersection(body_tokens)
            if not overlap:
                continue

            score = float(len(overlap)) / max(len(query_tokens), 1)
            provenance = Provenance(
                source_id="kanker.nl",
                title=title,
                url=url,
                canonical_url=url,
                publisher="KWF / NFK / IKNL",
                excerpt=_excerpt(text, query),
                metadata={"kankersoort": payload.get("kankersoort")},
            )
            document = SourceDocument(
                document_id=url,
                source_id="kanker.nl",
                title=title,
                url=url,
                content_type="text/plain",
                text=text,
                metadata={"kankersoort": payload.get("kankersoort")},
                provenance=provenance,
            )
            hits.append(
                SearchHit(
                    score=score,
                    excerpt=provenance.excerpt or "",
                    document=document,
                )
            )

        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:limit]

    def get_page(self, url: str) -> SourceDocument | None:
        payload = self.pages.get(url)
        if payload is None:
            return None
        text = payload.get("text", "")
        title = text.splitlines()[0].strip() if text else url.rsplit("/", 1)[-1]
        provenance = Provenance(
            source_id="kanker.nl",
            title=title,
            url=url,
            canonical_url=url,
            publisher="KWF / NFK / IKNL",
            excerpt=text[:240].replace("\n", " "),
            metadata={"kankersoort": payload.get("kankersoort")},
        )
        return SourceDocument(
            document_id=url,
            source_id="kanker.nl",
            title=title,
            url=url,
            content_type="text/plain",
            text=text,
            metadata={"kankersoort": payload.get("kankersoort")},
            provenance=provenance,
        )

    def robots_txt(self) -> str:
        response = httpx.get(self.ROBOTS_URL, timeout=self.settings.request_timeout_seconds)
        response.raise_for_status()
        return response.text

    def live_sample_page(self, url: str | None = None) -> dict[str, str | int]:
        sample_url = url or self.SAMPLE_URL
        response = httpx.get(sample_url, timeout=self.settings.request_timeout_seconds, follow_redirects=True)
        response.raise_for_status()
        title_match = re.search(r"<title[^>]*>(.*?)</title>", response.text, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else sample_url
        text = re.sub(r"<[^>]+>", " ", response.text)
        text = re.sub(r"\s+", " ", text).strip()
        return {
            "url": str(response.url),
            "status_code": response.status_code,
            "title": title,
            "excerpt": text[:400],
        }
