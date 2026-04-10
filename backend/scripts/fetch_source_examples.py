from __future__ import annotations

import json
from pathlib import Path

from app.config import get_settings
from app.connectors.firecrawl_client import FirecrawlClient, FirecrawlUnavailableError
from app.connectors.kanker_nl import LocalKankerNLDataset
from app.connectors.kankeratlas import KankerAtlasClient
from app.connectors.nkr_cijfers import NKRCijfersClient
from app.connectors.publications import PublicationsConnector
from app.connectors.iknl import IKNLWebConnector
from app.connectors.richtlijnendatabase import RichtlijnendatabaseConnector


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    settings = get_settings()
    output_dir = settings.sample_output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    nkr = NKRCijfersClient(settings)
    atlas = KankerAtlasClient(settings)
    kanker = LocalKankerNLDataset(settings)
    firecrawl = FirecrawlClient(settings)
    iknl = IKNLWebConnector(firecrawl)
    richtlijn = RichtlijnendatabaseConnector(firecrawl)
    publications = PublicationsConnector(settings, firecrawl)

    write_json(output_dir / "nkr_navigation.json", nkr.navigation_items())
    write_json(output_dir / "nkr_stage_distribution_2024.json", nkr.example_stage_distribution())
    write_json(output_dir / "kankeratlas_filters.json", atlas.filters())
    write_json(output_dir / "kankeratlas_lung_pc3.json", atlas.cancer_data(11, 3, 3))
    write_json(
        output_dir / "kanker_nl_search_darmkanker.json",
        [hit.model_dump(mode="json") for hit in kanker.search("darmkanker behandeling", limit=3)],
    )
    write_json(
        output_dir / "publications_local_manifest.json",
        {
            "reports": publications.list_local_reports(),
            "scientific_publications": publications.list_local_publications(),
            "web_report_pages": publications.REPORT_PAGES,
        },
    )
    write_json(output_dir / "kanker_nl_live_sample.json", kanker.live_sample_page())
    write_json(output_dir / "iknl_entrypoints.json", iknl.key_entrypoints())
    write_json(output_dir / "richtlijn_example.json", richtlijn.scrape_guideline())

    try:
        write_json(
            output_dir / "iknl_report_page_firecrawl.json",
            publications.scrape_report_page(publications.REPORT_PAGES[0]),
        )
    except FirecrawlUnavailableError as exc:
        write_json(output_dir / "firecrawl_status.json", {"status": "skipped", "reason": str(exc)})


if __name__ == "__main__":
    main()
