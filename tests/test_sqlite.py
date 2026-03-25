# tests/test_sqlite.py
import pytest
from src.db.sqlite import Database

@pytest.fixture
def db():
    return Database(":memory:")  # in-memory SQLite for tests

def test_create_job(db):
    job_id = db.create_job()
    assert len(job_id) == 36  # UUID format

def test_complete_job(db):
    job_id = db.create_job()
    meeting_id = "meeting-123"
    db.complete_job(job_id, meeting_id)
    job = db.get_job(job_id)
    assert job["status"] == "done"
    assert job["meeting_id"] == meeting_id

def test_fail_job(db):
    job_id = db.create_job()
    db.fail_job(job_id, "LLM timeout")
    job = db.get_job(job_id)
    assert job["status"] == "error"
    assert job["error"] == "LLM timeout"

def test_create_and_get_meeting(db):
    meeting = {
        "id": "m-001",
        "title": "Sprint Planning",
        "date": "2026-03-24",
        "duration_s": 3600.0,
        "speakers": ["SPEAKER_00", "SPEAKER_01"],
        "decisions": ["Launch beta in March"],
        "summary": "We decided to launch the beta.",
        "report_md": "# Sprint Planning\n\n...",
    }
    db.create_meeting(meeting)
    result = db.get_meeting("m-001")
    assert result["title"] == "Sprint Planning"
    assert result["speakers"] == ["SPEAKER_00", "SPEAKER_01"]
    assert result["decisions"] == ["Launch beta in March"]

def test_list_meetings(db):
    db.create_meeting({"id": "m-001", "title": "Meeting A", "date": "2026-03-20",
                        "speakers": [], "decisions": [], "summary": "", "report_md": ""})
    db.create_meeting({"id": "m-002", "title": "Meeting B", "date": "2026-03-24",
                        "speakers": [], "decisions": [], "summary": "", "report_md": ""})
    meetings = db.list_meetings()
    assert len(meetings) == 2

def test_create_and_list_action_items(db):
    db.create_meeting({"id": "m-001", "title": "T", "date": "2026-03-24",
                        "speakers": [], "decisions": [], "summary": "", "report_md": ""})
    db.create_action_item({
        "id": "a-001", "meeting_id": "m-001",
        "task": "Prepare demo", "owner": "SPEAKER_00",
        "due_date": "Friday", "status": "pending"
    })
    items = db.list_action_items(meeting_id="m-001")
    assert len(items) == 1
    assert items[0]["task"] == "Prepare demo"

def test_update_action_item_status(db):
    db.create_meeting({"id": "m-001", "title": "T", "date": "2026-03-24",
                        "speakers": [], "decisions": [], "summary": "", "report_md": ""})
    db.create_action_item({"id": "a-001", "meeting_id": "m-001",
                            "task": "T", "owner": "SPEAKER_00", "due_date": None, "status": "pending"})
    db.update_action_item_status("a-001", "done")
    item = db.get_action_item("a-001")
    assert item["status"] == "done"
