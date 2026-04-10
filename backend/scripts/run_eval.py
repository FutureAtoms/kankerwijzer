from __future__ import annotations

import json
from pathlib import Path

import yaml

from app.config import get_settings
from app.connectors.publications import PublicationsConnector
from app.connectors.firecrawl_client import FirecrawlClient
from app.retrieval.simple import SimpleMedicalRetriever


def load_cases(path: Path) -> list[dict]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def main() -> None:
    settings = get_settings()
    team_root = settings.team_root
    cases_path = team_root / "backend" / "eval" / "golden_questions.yaml"
    cases = load_cases(cases_path)

    retriever = SimpleMedicalRetriever(settings)
    publications = PublicationsConnector(settings, FirecrawlClient(settings))

    results = []
    passed = 0

    for case in cases:
        query = case["query"]
        expected_sources = set(case["expected_sources"])
        expect_refusal = case["expect_refusal"]

        if "reports and scientific publications" in query.lower():
            manifest = {
                "reports": publications.list_local_reports(),
                "scientific_publications": publications.list_local_publications(),
            }
            result = {
                "id": case["id"],
                "status": "pass" if manifest["reports"] and manifest["scientific_publications"] else "fail",
                "details": manifest,
            }
        else:
            retrieval = retriever.retrieve(query=query, audience=case["audience"])
            actual_sources = {hit.document.source_id for hit in retrieval.hits}
            refusal_ok = bool(retrieval.refusal_reason) if expect_refusal else not retrieval.refusal_reason
            source_ok = True if expect_refusal else bool(actual_sources.intersection(expected_sources))
            status = "pass" if refusal_ok and source_ok else "fail"
            result = {
                "id": case["id"],
                "status": status,
                "actual_sources": sorted(actual_sources),
                "expected_sources": sorted(expected_sources),
                "refusal_reason": retrieval.refusal_reason,
                "notes": retrieval.notes,
            }

        if result["status"] == "pass":
            passed += 1
        results.append(result)

    summary = {
        "passed": passed,
        "total": len(results),
        "results": results,
    }

    output_path = team_root / "artifacts" / "eval_report.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
