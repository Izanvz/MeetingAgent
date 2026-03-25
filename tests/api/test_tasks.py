import pytest
from fastapi.testclient import TestClient
from src.db.sqlite import Database


@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test.db")
    db = Database(db_path)
    db.create_meeting({"id": "m-001", "title": "T", "date": "2026-03-24",
                        "speakers": [], "decisions": [], "summary": "", "report_md": ""})
    db.create_action_item({"id": "a-001", "meeting_id": "m-001",
                            "task": "Prepare demo", "owner": "SPEAKER_00",
                            "due_date": "Friday", "status": "pending"})
    from src.api.main import create_app
    return TestClient(create_app(db_path=db_path))


def test_list_tasks(client):
    res = client.get("/tasks")
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_list_tasks_filter_by_status(client):
    res = client.get("/tasks?status=pending")
    assert len(res.json()) == 1
    res2 = client.get("/tasks?status=done")
    assert len(res2.json()) == 0


def test_update_task_status(client):
    res = client.patch("/tasks/a-001", json={"status": "done"})
    assert res.status_code == 200
    assert res.json()["status"] == "done"


def test_update_task_not_found(client):
    res = client.patch("/tasks/nonexistent", json={"status": "done"})
    assert res.status_code == 404
