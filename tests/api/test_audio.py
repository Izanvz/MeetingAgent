import io
import pytest
from unittest.mock import patch, AsyncMock

SAMPLE_SEGMENTS = [
    {"start": 0.0, "end": 5.0, "speaker": "Speaker 1", "text": "We need to finish the sprint by Friday."},
    {"start": 5.0, "end": 10.0, "speaker": "Speaker 1", "text": "Carlos will handle the Stripe integration."},
]

MP3_HEADER = b"\xff\xfb\x90\x00" + b"\x00" * 100  # minimal fake mp3


@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test.db")
    from src.api.main import create_app
    return create_app(db_path=db_path)


@pytest.fixture
def http(client):
    from fastapi.testclient import TestClient
    return TestClient(client)


def _upload(http, filename="meeting.mp3", content=MP3_HEADER, title="", meeting_date=""):
    return http.post(
        "/meetings/audio",
        files={"file": (filename, io.BytesIO(content), "audio/mpeg")},
        data={"title": title, "meeting_date": meeting_date},
    )


def test_audio_returns_202(http):
    with (
        patch("src.api.routes.audio._transcribe_and_analyze", new_callable=AsyncMock),
    ):
        res = _upload(http)
    assert res.status_code == 202
    body = res.json()
    assert "job_id" in body
    assert body["status"] == "processing"


def test_audio_invalid_extension(http):
    res = _upload(http, filename="notes.txt", content=b"hello")
    assert res.status_code == 400
    assert "Unsupported file type" in res.json()["detail"]


def test_audio_file_too_large(http):
    big = b"\x00" * (500 * 1024 * 1024 + 1)
    res = _upload(http, content=big)
    assert res.status_code == 413


def test_audio_accepted_extensions(http):
    for ext in (".mp3", ".mp4", ".wav", ".m4a", ".ogg", ".flac", ".webm"):
        with patch("src.api.routes.audio._transcribe_and_analyze", new_callable=AsyncMock):
            res = _upload(http, filename=f"audio{ext}")
        assert res.status_code == 202, f"Expected 202 for {ext}, got {res.status_code}"


def test_audio_default_title_from_filename(http):
    captured = {}

    async def fake_task(job_id, audio_bytes, ext, title, meeting_date):
        captured["title"] = title

    with patch("src.api.routes.audio._transcribe_and_analyze", side_effect=fake_task):
        _upload(http, filename="quarterly_review.mp3", title="")

    assert captured.get("title") == "quarterly_review"


def test_audio_explicit_title(http):
    captured = {}

    async def fake_task(job_id, audio_bytes, ext, title, meeting_date):
        captured["title"] = title

    with patch("src.api.routes.audio._transcribe_and_analyze", side_effect=fake_task):
        _upload(http, filename="audio.mp3", title="Sprint Planning Q1")

    assert captured.get("title") == "Sprint Planning Q1"


def test_audio_job_persisted_in_db(http, client):
    with patch("src.api.routes.audio._transcribe_and_analyze", new_callable=AsyncMock):
        res = _upload(http)
    job_id = res.json()["job_id"]

    job_res = http.get(f"/jobs/{job_id}")
    assert job_res.status_code == 200
    assert job_res.json()["job_id"] == job_id
