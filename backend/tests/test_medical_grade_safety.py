from app.models import Provenance, SearchHit, SourceDocument
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
