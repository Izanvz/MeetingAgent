import pytest
from fastapi.testclient import TestClient
from src.db.sqlite import Database


@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test.db")
    db = Database(db_path)
    db.create_meeting({"id": "m-001", "title": "Sprint Planning", "date": "2026-03-24",
                        "speakers": ["SPEAKER_00"], "decisions": ["Launch beta"],
                        "summary": "Agreed to launch.", "report_md": "# Report"})
    from src.api.main import create_app
    app = create_app(db_path=db_path)
    return TestClient(app)


def test_list_meetings(client):
    res = client.get("/meetings")
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["title"] == "Sprint Planning"


def test_get_meeting(client):
    res = client.get("/meetings/m-001")
    assert res.status_code == 200
    assert res.json()["decisions"] == ["Launch beta"]


def test_get_meeting_not_found(client):
    res = client.get("/meetings/nonexistent")
    assert res.status_code == 404
