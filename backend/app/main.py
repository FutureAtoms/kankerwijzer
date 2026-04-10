from __future__ import annotations

from fastapi import FastAPI, HTTPException

from app.agent.orchestrator import MedicalAnswerOrchestrator
from app.config import get_settings
from app.connectors.firecrawl_client import FirecrawlClient, FirecrawlUnavailableError
from app.connectors.iknl import IKNLWebConnector
from app.connectors.kanker_nl import LocalKankerNLDataset
from app.connectors.kankeratlas import KankerAtlasClient
from app.connectors.nkr_cijfers import NKRCijfersClient
from app.connectors.publications import PublicationsConnector
from app.connectors.richtlijnendatabase import RichtlijnendatabaseConnector
from app.models import FirecrawlRequest, ParsePdfRequest, QuestionRequest
from app.retrieval.hybrid import HybridMedicalRetriever
from app.retrieval.simple import SimpleMedicalRetriever
from app.source_registry import list_approved_sources
from app.verification import SourceVerifier

settings = get_settings()
app = FastAPI(title=settings.app_name)

nkr_client = NKRCijfersClient(settings)
kankeratlas_client = KankerAtlasClient(settings)
kanker_nl_dataset = LocalKankerNLDataset(settings)
firecrawl_client = FirecrawlClient(settings)
iknl_connector = IKNLWebConnector(firecrawl_client)
richtlijn_connector = RichtlijnendatabaseConnector(firecrawl_client)
publications_connector = PublicationsConnector(settings, firecrawl_client)
simple_retriever = SimpleMedicalRetriever(settings)
hybrid_retriever = HybridMedicalRetriever(settings)
answerer = MedicalAnswerOrchestrator(settings)
verifier = SourceVerifier(settings)


def _raise_optional_dependency(exc: Exception) -> None:
    raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}


@app.get("/sources")
def sources():
    return list_approved_sources()


@app.get("/sources/kanker-nl/search")
def kanker_nl_search(q: str, limit: int = 5):
    return kanker_nl_dataset.search(q, limit=limit)


@app.get("/sources/kanker-nl/robots")
def kanker_nl_robots():
    return {"url": kanker_nl_dataset.ROBOTS_URL, "content": kanker_nl_dataset.robots_txt()}


@app.get("/sources/kanker-nl/live-sample")
def kanker_nl_live_sample():
    return kanker_nl_dataset.live_sample_page()


@app.post("/sources/nkr/navigation")
def nkr_navigation(language: str = "nl-NL"):
    return nkr_client.navigation_items(language=language)


@app.post("/sources/nkr/configuration")
def nkr_configuration(code: str, language: str = "nl-NL"):
    return nkr_client.configuration(code=code, language=language)


@app.post("/sources/nkr/filter-groups")
def nkr_filter_groups(code: str, language: str = "nl-NL"):
    return nkr_client.filter_groups(code=code, language=language)


@app.post("/sources/nkr/data")
def nkr_data(body: dict):
    return nkr_client.data(body)


@app.get("/sources/nkr/example-stage-distribution")
def nkr_example_stage_distribution(year: int = 2024):
    return nkr_client.example_stage_distribution(year=year)


@app.get("/sources/kankeratlas/filters")
def kankeratlas_filters():
    return kankeratlas_client.filters()


@app.get("/sources/kankeratlas/cancer-groups")
def kankeratlas_cancer_groups(locale: str = "nl"):
    return kankeratlas_client.cancer_groups(locale=locale)


@app.get("/sources/kankeratlas/postcodes/{digits}")
def kankeratlas_postcodes(digits: int):
    return kankeratlas_client.postcodes(digits=digits)


@app.get("/sources/kankeratlas/cancer-data/{cancer_group}/{sex}/{postcode_digits}")
def kankeratlas_cancer_data(cancer_group: int, sex: int, postcode_digits: int):
    return kankeratlas_client.cancer_data(
        cancer_group=cancer_group,
        sex=sex,
        postcode_digits=postcode_digits,
    )


@app.get("/sources/publications/local")
def publications_local():
    return {
        "reports": publications_connector.list_local_reports(),
        "scientific_publications": publications_connector.list_local_publications(),
        "web_report_pages": publications_connector.REPORT_PAGES,
    }


@app.get("/sources/publications/index")
def publications_index():
    return publications_connector.scrape_publications_index()


@app.get("/sources/publications/report-pages")
def publications_report_pages():
    return publications_connector.scrape_report_pages()


@app.post("/sources/publications/parse")
def publications_parse(request: ParsePdfRequest):
    try:
        return publications_connector.parse_local_pdf(request.path)
    except Exception as exc:
        _raise_optional_dependency(exc)


@app.post("/sources/firecrawl/scrape")
def firecrawl_scrape(request: FirecrawlRequest):
    try:
        return firecrawl_client.scrape(request.url, formats=request.formats)
    except FirecrawlUnavailableError as exc:
        _raise_optional_dependency(exc)


@app.post("/sources/firecrawl/crawl")
def firecrawl_crawl(request: FirecrawlRequest):
    try:
        return firecrawl_client.crawl(
            url=request.url,
            limit=request.limit,
            include_paths=request.include_paths,
            exclude_paths=request.exclude_paths,
            formats=request.formats,
        )
    except FirecrawlUnavailableError as exc:
        _raise_optional_dependency(exc)


@app.get("/sources/iknl/scrape")
def iknl_scrape(url: str):
    try:
        return iknl_connector.scrape_page(url)
    except FirecrawlUnavailableError as exc:
        _raise_optional_dependency(exc)


@app.get("/sources/iknl/entrypoints")
def iknl_entrypoints():
    return iknl_connector.key_entrypoints()


@app.get("/sources/richtlijnendatabase/example")
def richtlijn_example():
    try:
        return richtlijn_connector.scrape_guideline()
    except FirecrawlUnavailableError as exc:
        _raise_optional_dependency(exc)


@app.get("/sources/verify/all")
def verify_all_sources():
    return verifier.verify_all()


@app.post("/agent/retrieve")
def agent_retrieve(request: QuestionRequest):
    return hybrid_retriever.retrieve(
        query=request.query,
        audience=request.audience,
        limit=request.limit,
    )


@app.post("/agent/retrieve/simple")
def agent_retrieve_simple(request: QuestionRequest):
    """Legacy endpoint using SimpleMedicalRetriever (for comparison/fallback)."""
    return simple_retriever.retrieve(
        query=request.query,
        audience=request.audience,
        limit=request.limit,
    )


@app.post("/agent/answer")
def agent_answer(request: QuestionRequest):
    return answerer.answer(
        query=request.query,
        audience=request.audience,
        limit=request.limit,
    )
