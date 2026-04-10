"""Evaluation pipeline for KankerWijzer golden questions.

Runs each question through the /agent/retrieve endpoint (via HTTP or direct call),
checks: has hits OR has refusal_reason (as appropriate),
source whitelist compliance, and refusal accuracy.
Outputs JSON report to eval/results/eval_report.json.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
import yaml

from app.config import get_settings
from app.connectors.firecrawl_client import FirecrawlClient
from app.connectors.publications import PublicationsConnector
from app.source_registry import list_approved_sources


def load_cases(path: Path) -> list[dict]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


APPROVED_SOURCES: set[str] = set()


def _init_approved_sources() -> None:
    global APPROVED_SOURCES
    try:
        sources = list_approved_sources()
        APPROVED_SOURCES = {s.source_id for s in sources}
    except Exception:
        # Fallback: known source IDs
        APPROVED_SOURCES = {
            "kanker.nl",
            "nkr-cijfers",
            "kankeratlas",
            "richtlijnendatabase",
            "iknl.nl",
            "iknl-reports",
            "scientific-publications",
        }


def evaluate_via_http(case: dict, base_url: str) -> dict:
    """Call /agent/retrieve over HTTP and evaluate the result."""
    try:
        response = httpx.post(
            f"{base_url}/agent/retrieve",
            json={
                "query": case["query"],
                "audience": case.get("audience", "patient"),
                "limit": 5,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        return {
            "id": case["id"],
            "status": "error",
            "error": str(exc),
        }

    return _evaluate_result(case, data)


def evaluate_direct(case: dict) -> dict:
    """Call the retriever directly (no HTTP server needed)."""
    from app.retrieval.hybrid import HybridMedicalRetriever

    settings = get_settings()

    # Special case: publications listing
    if "reports and scientific publications" in case["query"].lower():
        publications = PublicationsConnector(settings, FirecrawlClient(settings))
        manifest = {
            "reports": publications.list_local_reports(),
            "scientific_publications": publications.list_local_publications(),
        }
        has_data = bool(manifest.get("reports")) or bool(manifest.get("scientific_publications"))
        return {
            "id": case["id"],
            "status": "pass" if has_data else "fail",
            "details": manifest,
            "checks": {
                "has_results": has_data,
                "refusal_correct": True,
                "source_whitelist_ok": True,
            },
        }

    retriever = HybridMedicalRetriever(settings)
    try:
        retrieval = retriever.retrieve(
            query=case["query"],
            audience=case.get("audience", "patient"),
        )
        data = {
            "query": retrieval.query,
            "audience": retrieval.audience,
            "hits": [
                {
                    "score": h.score,
                    "document": {
                        "source_id": h.document.source_id,
                        "url": h.document.url,
                        "title": h.document.title,
                    },
                }
                for h in retrieval.hits
            ],
            "refusal_reason": retrieval.refusal_reason,
            "notes": retrieval.notes,
        }
    except Exception as exc:
        return {
            "id": case["id"],
            "status": "error",
            "error": str(exc),
        }

    return _evaluate_result(case, data)


def _evaluate_result(case: dict, data: dict) -> dict:
    """Core evaluation logic shared between HTTP and direct modes."""
    expected_sources = set(case.get("expected_sources", []))
    expect_refusal = case.get("expect_refusal", False)

    hits = data.get("hits", [])
    refusal_reason = data.get("refusal_reason")
    notes = data.get("notes", [])

    actual_sources: set[str] = set()
    for hit in hits:
        doc = hit.get("document", {})
        sid = doc.get("source_id", "")
        actual_sources.add(sid)

    # Check 1: has hits OR has refusal_reason
    has_results = len(hits) > 0 or refusal_reason is not None

    # Check 2: refusal accuracy
    if expect_refusal:
        refusal_correct = refusal_reason is not None
    else:
        refusal_correct = refusal_reason is None

    # Check 3: source whitelist compliance (only relevant for non-refusal cases)
    source_whitelist_ok = True
    non_whitelisted: list[str] = []
    if not expect_refusal:
        for sid in actual_sources:
            if sid and sid not in APPROVED_SOURCES:
                source_whitelist_ok = False
                non_whitelisted.append(sid)

    # Check 4: expected sources found (only for non-refusal cases)
    source_match = True
    if not expect_refusal and expected_sources:
        source_match = bool(actual_sources.intersection(expected_sources))

    # Overall pass/fail
    status = "pass" if (has_results and refusal_correct and source_whitelist_ok and (source_match or expect_refusal)) else "fail"

    return {
        "id": case["id"],
        "status": status,
        "actual_sources": sorted(actual_sources),
        "expected_sources": sorted(expected_sources),
        "refusal_reason": refusal_reason,
        "notes": notes,
        "checks": {
            "has_results": has_results,
            "refusal_correct": refusal_correct,
            "source_whitelist_ok": source_whitelist_ok,
            "source_match": source_match,
            "non_whitelisted_sources": non_whitelisted,
        },
    }


def main() -> None:
    settings = get_settings()
    team_root = settings.team_root
    cases_path = team_root / "backend" / "eval" / "golden_questions.yaml"
    cases = load_cases(cases_path)

    _init_approved_sources()

    # Determine evaluation mode: HTTP if server URL provided, else direct
    base_url = None
    if len(sys.argv) > 1:
        base_url = sys.argv[1].rstrip("/")

    results: list[dict] = []
    passed = 0
    failed = 0
    errors = 0

    print(f"Running {len(cases)} evaluation cases...")
    print(f"Mode: {'HTTP (' + base_url + ')' if base_url else 'direct'}")
    print(f"Approved sources: {sorted(APPROVED_SOURCES)}")
    print("-" * 60)

    for case in cases:
        if base_url:
            result = evaluate_via_http(case, base_url)
        else:
            result = evaluate_direct(case)

        status = result["status"]
        if status == "pass":
            passed += 1
            marker = "PASS"
        elif status == "error":
            errors += 1
            marker = "ERR "
        else:
            failed += 1
            marker = "FAIL"

        print(f"  [{marker}] {case['id']}")
        if status == "fail":
            checks = result.get("checks", {})
            if not checks.get("refusal_correct"):
                print(f"         -> Refusal mismatch (expected={case.get('expect_refusal')}, got={result.get('refusal_reason')})")
            if not checks.get("source_match"):
                print(f"         -> Source mismatch (expected={case.get('expected_sources')}, got={result.get('actual_sources')})")
            if not checks.get("source_whitelist_ok"):
                print(f"         -> Non-whitelisted sources: {checks.get('non_whitelisted_sources')}")

        results.append(result)

    print("-" * 60)
    total = len(results)
    print(f"Results: {passed}/{total} passed, {failed} failed, {errors} errors")
    if total > 0:
        print(f"Pass rate: {passed / total * 100:.1f}%")

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": total,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "pass_rate": round(passed / total * 100, 1) if total > 0 else 0,
        "approved_sources": sorted(APPROVED_SOURCES),
        "results": results,
    }

    # Write to eval/results/
    output_dir = team_root / "backend" / "eval" / "results"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "eval_report.json"
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nReport written to: {output_path}")

    # Also write to artifacts for backwards compatibility
    artifacts_path = team_root / "artifacts" / "eval_report.json"
    artifacts_path.parent.mkdir(parents=True, exist_ok=True)
    artifacts_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
