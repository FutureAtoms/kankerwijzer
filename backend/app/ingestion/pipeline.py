"""Master orchestrator for the KankerWijzer data ingestion pipeline.

Run via: uv run python -m app.ingestion.pipeline
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.ingestion.chunker import chunk_text
from app.ingestion.pdf_manifest import PDF_MANIFEST
from app.ingestion.postgres_writer import (
    ChunkRow,
    DocumentRow,
    PostgresWriter,
    SourceRow,
    make_chunk_id,
)
from app.source_registry import SOURCE_REGISTRY


def _sha256_hex(text: str, length: int = 16) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def _extract_pdf_text(pdf_path: Path) -> list[tuple[int, str]]:
    """Extract text from a PDF, returning list of (page_number, text).

    Uses PyMuPDF (pymupdf) as primary extractor.
    """
    try:
        import pymupdf  # noqa: F811

        doc = pymupdf.open(str(pdf_path))
        pages = []
        for i, page in enumerate(doc):
            text = page.get_text()
            if text and text.strip():
                pages.append((i + 1, text))
        doc.close()
        return pages
    except ImportError:
        pass

    # Fallback: try fitz (older PyMuPDF import name)
    try:
        import fitz

        doc = fitz.open(str(pdf_path))
        pages = []
        for i, page in enumerate(doc):
            text = page.get_text()
            if text and text.strip():
                pages.append((i + 1, text))
        doc.close()
        return pages
    except ImportError:
        print(f"  WARNING: No PDF library available, skipping {pdf_path.name}")
        return []


# ---------------------------------------------------------------------------
# Phase 1: kanker.nl JSON dataset
# ---------------------------------------------------------------------------

def ingest_kanker_nl(writer: PostgresWriter, settings: Any) -> dict[str, int]:
    """Load the pre-provided kanker.nl JSON and write to Postgres."""
    print("\n=== Phase 1: kanker.nl (local JSON dataset) ===")
    dataset_path = settings.kanker_dataset_path
    if not dataset_path.exists():
        print(f"  SKIP: {dataset_path} not found")
        return {"documents": 0, "chunks": 0}

    src = SOURCE_REGISTRY["kanker.nl"]
    writer.upsert_source(SourceRow(
        source_id=src.source_id,
        name=src.name,
        publisher=src.publisher,
        trust_tier=src.trust_tier,
        access_mode=src.access_mode,
    ))

    data: dict[str, dict[str, str]] = json.loads(dataset_path.read_text(encoding="utf-8"))
    print(f"  Loaded {len(data)} pages from {dataset_path.name}")

    doc_rows: list[DocumentRow] = []
    all_chunks: list[ChunkRow] = []

    for url, payload in data.items():
        text = payload.get("text", "")
        if not text.strip():
            continue

        document_id = _sha256_hex(url)
        title_line = text.splitlines()[0].strip() if text.splitlines() else url.rsplit("/", 1)[-1]
        title = title_line[:200] if title_line else url.rsplit("/", 1)[-1]
        checksum = _sha256_hex(text, length=32)

        doc_rows.append(DocumentRow(
            document_id=document_id,
            source_id="kanker.nl",
            canonical_url=url,
            title=title,
            content_type="text/html",
            language="nl",
            checksum=checksum,
        ))

        chunks = chunk_text(text)
        for idx, chunk in enumerate(chunks):
            chunk_id = make_chunk_id(document_id, idx)
            all_chunks.append(ChunkRow(
                chunk_id=chunk_id,
                document_id=document_id,
                chunk_index=idx,
                chunk_text=chunk,
                citation_url=url,
            ))

    n_docs = writer.upsert_documents(doc_rows)
    n_chunks = writer.upsert_chunks(all_chunks)
    print(f"  Documents: {n_docs}, Chunks: {n_chunks}")
    return {"documents": n_docs, "chunks": n_chunks}


# ---------------------------------------------------------------------------
# Phase 2 & 3: PDF ingestion (reports + scientific publications)
# ---------------------------------------------------------------------------

def _ingest_pdf_dir(
    writer: PostgresWriter,
    pdf_dir: Path,
    phase_label: str,
) -> dict[str, int]:
    """Ingest all PDFs in *pdf_dir* using the PDF_MANIFEST."""
    print(f"\n=== {phase_label} ===")
    if not pdf_dir.exists():
        print(f"  SKIP: {pdf_dir} not found")
        return {"documents": 0, "chunks": 0}

    # Ensure all relevant sources exist
    for manifest_entry in PDF_MANIFEST.values():
        sid = manifest_entry["source_id"]
        if sid in SOURCE_REGISTRY:
            src = SOURCE_REGISTRY[sid]
            writer.upsert_source(SourceRow(
                source_id=src.source_id,
                name=src.name,
                publisher=src.publisher,
                trust_tier=src.trust_tier,
                access_mode=src.access_mode,
            ))

    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    print(f"  Found {len(pdf_files)} PDF files in {pdf_dir.name}/")

    total_docs = 0
    total_chunks = 0

    for pdf_path in pdf_files:
        filename = pdf_path.name
        manifest = PDF_MANIFEST.get(filename)
        if not manifest:
            print(f"  WARNING: {filename} not in manifest, skipping")
            continue

        canonical_url = manifest["canonical_url"]
        source_id = manifest["source_id"]
        title = manifest["title"]

        pages = _extract_pdf_text(pdf_path)
        if not pages:
            print(f"  WARNING: No text extracted from {filename}")
            continue

        full_text = "\n\n".join(text for _, text in pages)
        document_id = _sha256_hex(canonical_url)
        checksum = _sha256_hex(full_text, length=32)

        writer.upsert_documents([DocumentRow(
            document_id=document_id,
            source_id=source_id,
            canonical_url=canonical_url,
            title=title,
            content_type="application/pdf",
            language="nl",
            checksum=checksum,
        )])
        total_docs += 1

        # Delete existing chunks for this document (re-ingest safely)
        writer.delete_chunks_for_document(document_id)

        # Chunk with page-level awareness
        chunk_rows: list[ChunkRow] = []
        chunk_idx = 0

        for page_num, page_text in pages:
            page_chunks = chunk_text(page_text)
            for chunk in page_chunks:
                chunk_id = make_chunk_id(document_id, chunk_idx)
                chunk_rows.append(ChunkRow(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    chunk_index=chunk_idx,
                    chunk_text=chunk,
                    citation_url=canonical_url,
                    page_number=page_num,
                ))
                chunk_idx += 1

        n = writer.upsert_chunks(chunk_rows)
        total_chunks += n
        print(f"  {filename}: {len(pages)} pages, {n} chunks")

    print(f"  Total - Documents: {total_docs}, Chunks: {total_chunks}")
    return {"documents": total_docs, "chunks": total_chunks}


def ingest_reports(writer: PostgresWriter, settings: Any) -> dict[str, int]:
    return _ingest_pdf_dir(writer, settings.reports_dir, "Phase 2: PDF reports (iknl-reports)")


def ingest_scientific_publications(writer: PostgresWriter, settings: Any) -> dict[str, int]:
    return _ingest_pdf_dir(writer, settings.scientific_publications_dir, "Phase 3: Scientific publications")


# ---------------------------------------------------------------------------
# Phase 4: NKR metadata
# ---------------------------------------------------------------------------

def ingest_nkr_metadata(writer: PostgresWriter, settings: Any) -> dict[str, int]:
    """Fetch NKR navigation items and store as metadata documents."""
    print("\n=== Phase 4: NKR metadata (API) ===")
    import httpx

    src = SOURCE_REGISTRY["nkr-cijfers"]
    writer.upsert_source(SourceRow(
        source_id=src.source_id,
        name=src.name,
        publisher=src.publisher,
        trust_tier=src.trust_tier,
        access_mode=src.access_mode,
    ))

    try:
        resp = httpx.post(
            "https://api.nkr-cijfers.iknl.nl/api/navigation-items?format=json",
            json={"language": "nl-NL"},
            timeout=30.0,
        )
        resp.raise_for_status()
        nav_items = resp.json()
    except Exception as exc:
        print(f"  WARNING: NKR API call failed: {exc}")
        return {"documents": 0, "chunks": 0}

    if not isinstance(nav_items, list):
        # Might be nested; try to extract
        if isinstance(nav_items, dict) and "items" in nav_items:
            nav_items = nav_items["items"]
        else:
            nav_items = [nav_items] if nav_items else []

    doc_rows: list[DocumentRow] = []
    all_chunks: list[ChunkRow] = []

    def _process_nav(item: dict, depth: int = 0) -> None:
        code = item.get("code", "")
        label = item.get("label", item.get("name", code))
        if not code:
            return

        url = f"https://nkr-cijfers.iknl.nl/{code}"
        document_id = _sha256_hex(url)
        text = f"{label}\n\nNKR-cijfers navigatie: {code}"

        # Include any description or sub-info
        if item.get("description"):
            text += f"\n\n{item['description']}"

        doc_rows.append(DocumentRow(
            document_id=document_id,
            source_id="nkr-cijfers",
            canonical_url=url,
            title=label,
            content_type="application/json",
            language="nl",
            checksum=_sha256_hex(text, 32),
        ))

        chunks = chunk_text(text)
        for idx, chunk in enumerate(chunks):
            chunk_id = make_chunk_id(document_id, idx)
            all_chunks.append(ChunkRow(
                chunk_id=chunk_id,
                document_id=document_id,
                chunk_index=idx,
                chunk_text=chunk,
                citation_url=url,
            ))

        # Recurse into children
        for child in item.get("children", []):
            _process_nav(child, depth + 1)

    for item in nav_items:
        _process_nav(item)

    n_docs = writer.upsert_documents(doc_rows)
    n_chunks = writer.upsert_chunks(all_chunks)
    print(f"  Navigation items: {len(doc_rows)}, Documents: {n_docs}, Chunks: {n_chunks}")
    return {"documents": n_docs, "chunks": n_chunks}


# ---------------------------------------------------------------------------
# Phase 5: Cancer Atlas metadata
# ---------------------------------------------------------------------------

def ingest_kankeratlas_metadata(writer: PostgresWriter, settings: Any) -> dict[str, int]:
    """Fetch Cancer Atlas filters and cancer groups, store as metadata."""
    print("\n=== Phase 5: Cancer Atlas metadata (API) ===")
    import httpx

    src = SOURCE_REGISTRY["kankeratlas"]
    writer.upsert_source(SourceRow(
        source_id=src.source_id,
        name=src.name,
        publisher=src.publisher,
        trust_tier=src.trust_tier,
        access_mode=src.access_mode,
    ))

    doc_rows: list[DocumentRow] = []
    all_chunks: list[ChunkRow] = []

    # Fetch filters
    try:
        resp = httpx.get(
            "https://kankeratlas.iknl.nl/locales/nl/filters.json",
            timeout=30.0,
        )
        resp.raise_for_status()
        filters_data = resp.json()

        url = "https://kankeratlas.iknl.nl/locales/nl/filters.json"
        document_id = _sha256_hex(url)
        text = f"Kankeratlas filters\n\n{json.dumps(filters_data, ensure_ascii=False, indent=2)}"
        doc_rows.append(DocumentRow(
            document_id=document_id,
            source_id="kankeratlas",
            canonical_url="https://kankeratlas.iknl.nl",
            title="Kankeratlas - Filters en kankersoorten",
            content_type="application/json",
            language="nl",
            checksum=_sha256_hex(text, 32),
        ))

        chunks = chunk_text(text)
        for idx, chunk in enumerate(chunks):
            chunk_id = make_chunk_id(document_id, idx)
            all_chunks.append(ChunkRow(
                chunk_id=chunk_id,
                document_id=document_id,
                chunk_index=idx,
                chunk_text=chunk,
                citation_url="https://kankeratlas.iknl.nl",
            ))
        print(f"  Filters: {len(chunks)} chunks")
    except Exception as exc:
        print(f"  WARNING: Kankeratlas filters API failed: {exc}")

    # Fetch cancer groups
    try:
        resp = httpx.get(
            "https://iknl-atlas-strapi-prod.azurewebsites.net/api/cancer-groups/cancergrppc?locale=nl",
            timeout=30.0,
        )
        resp.raise_for_status()
        cancer_groups = resp.json()

        # Process cancer groups - they may be a list or dict with 'data'
        items = cancer_groups
        if isinstance(cancer_groups, dict):
            items = cancer_groups.get("data", cancer_groups.get("items", [cancer_groups]))

        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    name = item.get("name", item.get("attributes", {}).get("name", ""))
                    item_id = item.get("grp", item.get("id", ""))
                    if not name:
                        continue
                    url = f"https://kankeratlas.iknl.nl/cancer-group/{item_id}"
                    document_id = _sha256_hex(url)
                    text = f"Kankeratlas: {name}\n\n{json.dumps(item, ensure_ascii=False, indent=2)}"
                    doc_rows.append(DocumentRow(
                        document_id=document_id,
                        source_id="kankeratlas",
                        canonical_url="https://kankeratlas.iknl.nl",
                        title=f"Kankeratlas - {name}",
                        content_type="application/json",
                        language="nl",
                        checksum=_sha256_hex(text, 32),
                    ))
                    chunks = chunk_text(text)
                    for idx, chunk in enumerate(chunks):
                        chunk_id = make_chunk_id(document_id, idx)
                        all_chunks.append(ChunkRow(
                            chunk_id=chunk_id,
                            document_id=document_id,
                            chunk_index=idx,
                            chunk_text=chunk,
                            citation_url="https://kankeratlas.iknl.nl",
                        ))

        print(f"  Cancer groups: {len(items) if isinstance(items, list) else 1} items")
    except Exception as exc:
        print(f"  WARNING: Kankeratlas cancer groups API failed: {exc}")

    n_docs = writer.upsert_documents(doc_rows)
    n_chunks = writer.upsert_chunks(all_chunks)
    print(f"  Total - Documents: {n_docs}, Chunks: {n_chunks}")
    return {"documents": n_docs, "chunks": n_chunks}


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline() -> dict[str, Any]:
    """Run the full ingestion pipeline and return a summary."""
    settings = get_settings()
    writer = PostgresWriter(settings.postgres_url)

    print("=" * 60)
    print("KankerWijzer Data Ingestion Pipeline")
    print("=" * 60)

    # Ensure DB schema exists
    print("\nEnsuring database schema...")
    writer.ensure_schema()
    print("  Schema OK")

    start_time = time.time()
    summary: dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "phases": {},
    }

    # Phase 1: kanker.nl
    result = ingest_kanker_nl(writer, settings)
    summary["phases"]["kanker.nl"] = result

    # Phase 2: PDF reports
    result = ingest_reports(writer, settings)
    summary["phases"]["iknl-reports"] = result

    # Phase 3: Scientific publications
    result = ingest_scientific_publications(writer, settings)
    summary["phases"]["scientific-publications"] = result

    # Phase 4: NKR metadata
    result = ingest_nkr_metadata(writer, settings)
    summary["phases"]["nkr-cijfers"] = result

    # Phase 5: Cancer Atlas metadata
    result = ingest_kankeratlas_metadata(writer, settings)
    summary["phases"]["kankeratlas"] = result

    # Phase 6: Knowledge graph (Neo4j) — optional, requires Anthropic API key
    try:
        from app.graphrag.builder import build_graph
        print("\n--- Phase 6: Knowledge Graph (Neo4j) ---")
        build_graph()
        summary["phases"]["knowledge-graph"] = {"status": "ok"}
    except SystemExit:
        print("  Skipped: ANTHROPIC_API_KEY not set or Neo4j unavailable")
        summary["phases"]["knowledge-graph"] = {"status": "skipped"}
    except Exception as exc:
        print(f"  Graph build failed (non-fatal): {exc}")
        summary["phases"]["knowledge-graph"] = {"status": "error", "error": str(exc)}

    elapsed = time.time() - start_time
    summary["elapsed_seconds"] = round(elapsed, 2)
    summary["finished_at"] = datetime.now(timezone.utc).isoformat()

    # Final counts
    counts = writer.get_counts()
    summary["totals"] = counts

    print("\n" + "=" * 60)
    print("INGESTION COMPLETE")
    print("=" * 60)
    print(f"  Sources:   {counts['sources']}")
    print(f"  Documents: {counts['documents']}")
    print(f"  Chunks:    {counts['chunks']}")
    print(f"  Elapsed:   {elapsed:.1f}s")

    # Save summary JSON
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "ingestion_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\n  Summary saved to {summary_path}")

    return summary


if __name__ == "__main__":
    run_pipeline()
