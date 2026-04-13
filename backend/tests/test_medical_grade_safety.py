from app.config import get_settings
from app.models import Provenance, SearchHit, SourceDocument
from app.retrieval.hybrid import HybridMedicalRetriever
from app.safety.abstention import check_low_coverage, extract_specific_cancer_terms


def _hit(*, title: str, text: str, source_id: str = "kanker.nl") -> SearchHit:
    provenance = Provenance(
        source_id=source_id,
        title=title,
        url=f"https://example.test/{title.replace(' ', '-').lower()}",
        excerpt=text[:200],
    )
    document = SourceDocument(
        document_id=title.lower().replace(" ", "-"),
        source_id=source_id,
        title=title,
        url=provenance.url,
        content_type="text",
        text=text,
        provenance=provenance,
    )
    return SearchHit(score=0.9, excerpt=text[:300], document=document)


def test_extract_specific_cancer_terms_skips_generic_kanker():
    assert extract_specific_cancer_terms("wat is kanker") == []
    assert extract_specific_cancer_terms("behandeling voor longkanker") == ["longkanker"]


def test_low_coverage_refuses_when_specific_cancer_term_is_missing():
    hits = [
        _hit(
            title="Chemotherapie bij een hersentumor",
            text="Chemotherapie kan worden ingezet als behandeling bij een hersentumor.",
        ),
        _hit(
            title="Behandeling van endeldarmkanker per stadium",
            text="Bij endeldarmkanker hangt de behandeling af van het stadium.",
        ),
    ]

    assert (
        check_low_coverage("behandeling voor xyzkanker", hits)
        == "low_coverage_specific_cancer"
    )


def test_low_coverage_allows_matching_specific_cancer_term():
    hits = [
        _hit(
            title="Symptomen van longkanker",
            text="Bij longkanker komen klachten zoals hoesten en vermoeidheid voor.",
        )
    ]

    assert check_low_coverage("symptomen longkanker", hits) is None


def test_geo_queries_prefer_cancer_atlas_over_nkr(monkeypatch):
    retriever = HybridMedicalRetriever(get_settings())
    atlas_hit = _hit(
        title="Cancer Atlas long cancer incidence by postcode",
        text="Regionale atlasgegevens per postcodegebied.",
        source_id="kankeratlas",
    )
    nkr_hit = _hit(
        title="NKR Cijfers incidence distribution per stadium",
        text="Landelijke incidentiecijfers uit de Nederlandse Kankerregistratie.",
        source_id="nkr-cijfers",
    )

    monkeypatch.setattr(retriever, "_fetch_kankeratlas", lambda query: [atlas_hit])
    monkeypatch.setattr(retriever, "_fetch_nkr", lambda query: [nkr_hit])

    hits = retriever._route_structured("Welke regio heeft de hoogste borstkanker incidentie?")
    assert hits[0].document.source_id == "kankeratlas"


def test_kankeratlas_fetch_uses_query_specific_group_and_filters(monkeypatch):
    retriever = HybridMedicalRetriever(get_settings())
    captured: dict[str, int] = {}

    def fake_cancer_data(cancer_group: int, sex: int, postcode_digits: int):
        captured.update(
            {
                "cancer_group": cancer_group,
                "sex": sex,
                "postcode_digits": postcode_digits,
            }
        )
        return {"res": [{"postcode": "1011", "p50": 12.8}]}

    monkeypatch.setattr(retriever.kankeratlas, "cancer_data", fake_cancer_data)

    hits = retriever._fetch_kankeratlas(
        "toon regionale longkanker cijfers voor vrouwen per pc4"
    )

    assert captured == {
        "cancer_group": 11,
        "sex": 2,
        "postcode_digits": 4,
    }
    assert "longkanker" in hits[0].document.title.lower()


def test_guideline_queries_prefer_richtlijn_route(monkeypatch):
    retriever = HybridMedicalRetriever(get_settings())
    guideline_hit = _hit(
        title="Startpagina - Prostaatcarcinoom - Richtlijn - Richtlijnendatabase",
        text="Overzicht van de prostaatcarcinoomrichtlijn.",
        source_id="richtlijnendatabase",
    )

    monkeypatch.setattr(retriever, "_fetch_richtlijn", lambda query: [guideline_hit])

    hits = retriever._route_structured("Find the prostate carcinoma guideline overview.")
    assert hits[0].document.source_id == "richtlijnendatabase"


def test_out_of_scope_queries_are_rejected_before_retrieval():
    retriever = HybridMedicalRetriever(get_settings())

    result = retriever.retrieve("Wat is een goed recept voor appeltaart?")

    assert result.refusal_reason is not None
    assert "buiten het onderwerp" in result.refusal_reason.lower()


def test_years_are_not_mistaken_for_postcodes_in_stats_queries(monkeypatch):
    retriever = HybridMedicalRetriever(get_settings())
    atlas_hit = _hit(
        title="Cancer Atlas result",
        text="Regionale atlasgegevens.",
        source_id="kankeratlas",
    )
    nkr_hit = _hit(
        title="NKR result",
        text="Landelijke registratiedata per jaar en stadium.",
        source_id="nkr-cijfers",
    )

    monkeypatch.setattr(retriever, "_fetch_kankeratlas", lambda query: [atlas_hit])
    monkeypatch.setattr(retriever, "_fetch_nkr", lambda query: [nkr_hit])

    hits = retriever._route_structured(
        "Show the incidence distribution per stadium for all cancers for 2024."
    )
    assert hits[0].document.source_id == "nkr-cijfers"


def test_nkr_request_parser_handles_english_filtered_count_query():
    retriever = HybridMedicalRetriever(get_settings())

    parsed = retriever._parse_nkr_request("how many women in 2024 had ovarian cancer")

    assert parsed == {
        "cancer_type": "eierstokkanker",
        "year": 2024,
        "sex": "vrouw",
        "stat_type": "incidentie",
        "stage": "alle",
    }


def test_nkr_request_parser_handles_dutch_filtered_count_query():
    retriever = HybridMedicalRetriever(get_settings())

    parsed = retriever._parse_nkr_request(
        "hoeveel vrouwen kregen in 2024 eierstokkanker"
    )

    assert parsed == {
        "cancer_type": "eierstokkanker",
        "year": 2024,
        "sex": "vrouw",
        "stat_type": "incidentie",
        "stage": "alle",
    }


def test_nkr_fetch_uses_filtered_statistics_query(monkeypatch):
    retriever = HybridMedicalRetriever(get_settings())
    captured: dict[str, object] = {}

    def fake_query_statistics(*, cancer_type, year, sex, stat_type, stage):
        captured.update(
            {
                "cancer_type": cancer_type,
                "year": year,
                "sex": sex,
                "stat_type": stat_type,
                "stage": stage,
            }
        )
        return {
            "title": {
                "title": "Incidentie per jaar, Aantal",
            },
            "data": [
                {
                    "value": 1453.0,
                    "filterValues": [
                        {"filterCode": "filter/periode-van-diagnose", "code": "periode/1-jaar/2024"}
                    ],
                }
            ],
        }

    monkeypatch.setattr(retriever.nkr, "query_statistics", fake_query_statistics)

    hits = retriever._fetch_nkr("how many women in 2024 had ovarian cancer")

    assert captured == {
        "cancer_type": "eierstokkanker",
        "year": 2024,
        "sex": "vrouw",
        "stat_type": "incidentie",
        "stage": "alle",
    }
    assert hits[0].document.source_id == "nkr-cijfers"
    assert "1453" in hits[0].excerpt


def test_nkr_request_parser_handles_stage_specific_survival_query():
    retriever = HybridMedicalRetriever(get_settings())

    parsed = retriever._parse_nkr_request(
        "Wat zijn de 5-jaars overlevingscijfers voor stadium II colonkanker?"
    )

    assert parsed == {
        "cancer_type": "dikkedarmkanker",
        "year": 2024,
        "sex": "alle",
        "stat_type": "overleving",
        "stage": "ii",
    }


def test_nkr_fetch_passes_stage_filter_for_survival_query(monkeypatch):
    retriever = HybridMedicalRetriever(get_settings())
    captured: dict[str, object] = {}

    def fake_query_statistics(*, cancer_type, year, sex, stat_type, stage):
        captured.update(
            {
                "cancer_type": cancer_type,
                "year": year,
                "sex": sex,
                "stat_type": stat_type,
                "stage": stage,
            }
        )
        return {
            "title": {"title": "Overleving per jaar vanaf diagnose, Relatieve overleving"},
            "data": [{"value": 99.0}],
        }

    monkeypatch.setattr(retriever.nkr, "query_statistics", fake_query_statistics)

    hits = retriever._fetch_nkr(
        "wat zijn de 5-jaars overlevingscijfers voor stadium ii colonkanker?"
    )

    assert captured == {
        "cancer_type": "dikkedarmkanker",
        "year": 2024,
        "sex": "alle",
        "stat_type": "overleving",
        "stage": "ii",
    }
    assert "99.0%" in hits[0].excerpt
    assert "stadium II" in hits[0].excerpt


def test_mixed_stats_and_explanation_queries_merge_structured_and_vector_sources(monkeypatch):
    retriever = HybridMedicalRetriever(get_settings())
    nkr_hit = _hit(
        title="NKR incidentie borstkanker",
        text="Nieuwe diagnoses in 2024 voor borstkanker: 15539.",
        source_id="nkr-cijfers",
    )
    kanker_hit = _hit(
        title="Wat is borstkanker?",
        text="Borstkanker is kanker die in de borst ontstaat.",
        source_id="kanker.nl",
    )

    monkeypatch.setattr(retriever, "_fetch_nkr", lambda query: [nkr_hit])
    monkeypatch.setattr(retriever, "_vector_search", lambda query, limit=5: [kanker_hit])

    result = retriever.retrieve("Wat is borstkanker en hoe vaak komt het voor in Nederland?")

    assert [hit.document.source_id for hit in result.hits[:2]] == ["nkr-cijfers", "kanker.nl"]
