from __future__ import annotations

from pathlib import Path
from typing import Any


class DoclingUnavailableError(RuntimeError):
    pass


class DoclingParser:
    def _converter(self) -> Any:
        try:
            from docling.document_converter import DocumentConverter
        except ImportError as exc:
            raise DoclingUnavailableError(
                "Docling is not installed. Run `uv sync --extra docs`."
            ) from exc
        return DocumentConverter()

    def parse(self, source: str | Path) -> dict[str, Any]:
        converter = self._converter()
        result = converter.convert(str(source))
        markdown = result.document.export_to_markdown()
        return {
            "source": str(source),
            "markdown": markdown,
            "text_length": len(markdown),
        }
