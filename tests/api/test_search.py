import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

MOCK_RESULTS = [
    {"text": "We'll prepare the demo by Friday.", "speaker": "SPEAKER_00",
     "start": 0.0, "end": 4.0, "meeting_id": "m-001",
     "meeting_title": "Sprint Planning", "date": "2026-03-24"}
]


@pytest.fixture
def client():
    from src.api.main import create_app
    return TestClient(create_app())


def test_search_returns_results(client):
    with patch("src.api.routes.search.VectorStore") as MockStore:
        MockStore.return_value.search.return_value = MOCK_RESULTS
        res = client.post("/search", json={"query": "demo preparation", "top_k": 5})
    assert res.status_code == 200
    assert res.json()["results"][0]["speaker"] == "SPEAKER_00"


def test_search_empty_results(client):
    with patch("src.api.routes.search.VectorStore") as MockStore:
        MockStore.return_value.search.return_value = []
        res = client.post("/search", json={"query": "nonexistent topic"})
    assert res.status_code == 200
    assert res.json()["results"] == []
