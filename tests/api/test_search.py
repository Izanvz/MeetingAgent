from unittest.mock import MagicMock

MOCK_RESULTS = [
    {"text": "We'll prepare the demo by Friday.", "speaker": "SPEAKER_00",
     "start": 0.0, "end": 4.0, "meeting_id": "m-001",
     "meeting_title": "Sprint Planning", "date": "2026-03-24"}
]


def _mock_store(results):
    store = MagicMock()
    store.search.return_value = results
    return store


def test_search_returns_results():
    from src.api.main import create_app
    from src.api.deps import get_vector_store
    from fastapi.testclient import TestClient
    app = create_app()
    app.dependency_overrides[get_vector_store] = lambda: _mock_store(MOCK_RESULTS)
    res = TestClient(app).post("/search", json={"query": "demo preparation", "top_k": 5})
    assert res.status_code == 200
    assert res.json()["results"][0]["speaker"] == "SPEAKER_00"


def test_search_empty_results():
    from src.api.main import create_app
    from src.api.deps import get_vector_store
    from fastapi.testclient import TestClient
    app = create_app()
    app.dependency_overrides[get_vector_store] = lambda: _mock_store([])
    res = TestClient(app).post("/search", json={"query": "nonexistent topic"})
    assert res.status_code == 200
    assert res.json()["results"] == []
