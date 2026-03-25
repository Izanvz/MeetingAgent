import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

SAMPLE_PAYLOAD = {
    "title": "Sprint Planning",
    "date": "2026-03-24",
    "segments": [
        {"start": 0.0, "end": 4.0, "speaker": "SPEAKER_00",
         "text": "We need to deliver the module by Friday."}
    ]
}


@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test.db")
    from src.api.main import create_app
    return TestClient(create_app(db_path=db_path))


def test_analyze_returns_202(client):
    with patch("src.api.routes.analyze.run_agent", new_callable=AsyncMock):
        response = client.post("/analyze", json=SAMPLE_PAYLOAD)
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "processing"


def test_get_job_not_found(client):
    response = client.get("/jobs/nonexistent-id")
    assert response.status_code == 404


def test_get_job_processing(client):
    with patch("src.api.routes.analyze.run_agent", new_callable=AsyncMock):
        post_res = client.post("/analyze", json=SAMPLE_PAYLOAD)
    job_id = post_res.json()["job_id"]
    get_res = client.get(f"/jobs/{job_id}")
    assert get_res.status_code == 200
    assert get_res.json()["status"] in ("processing", "done", "error")
