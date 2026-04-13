from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_is_available():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_sources_endpoint_returns_trusted_registry():
    with TestClient(app) as client:
        response = client.get("/sources")

    assert response.status_code == 200
    payload = response.json()
    source_ids = {item["source_id"] for item in payload}
    assert "kanker.nl" in source_ids
    assert "nkr-cijfers" in source_ids
