from app.config import get_settings
from app.connectors.kanker_nl import LocalKankerNLDataset
from app.retrieval.simple import SimpleMedicalRetriever


def test_kanker_nl_search_returns_hits():
    dataset = LocalKankerNLDataset(get_settings())
    hits = dataset.search("darmkanker behandeling", limit=3)
    assert hits
    assert hits[0].document.source_id == "kanker.nl"


def test_personalized_treatment_question_is_refused():
    retriever = SimpleMedicalRetriever(get_settings())
    result = retriever.retrieve(
        "I have blood in my stool and weight loss, should I start chemotherapy?"
    )
    assert result.refusal_reason is not None
