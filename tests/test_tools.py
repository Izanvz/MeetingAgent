import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage

FAKE_ANALYSIS = """{
  "summary": "Team agreed to launch beta in March.",
  "decisions": ["Launch beta in March"],
  "participants": ["SPEAKER_00", "SPEAKER_01"]
}"""

FAKE_ACTIONS = """{
  "action_items": [
    {"task": "Prepare demo", "owner": "SPEAKER_00", "due_date": "Friday", "status": "pending"}
  ]
}"""

FAKE_REPORT = "# Sprint Planning\n\n## Summary\nTeam agreed to launch beta in March."

def make_mock_llm(content: str):
    mock = MagicMock()
    mock.invoke.return_value = AIMessage(content=content)
    return mock

def test_analyze_transcript():
    with patch("src.agent.tools.get_llm", return_value=make_mock_llm(FAKE_ANALYSIS)):
        from src.agent.tools import analyze_transcript
        segments = [
            {"start": 0.0, "end": 4.0, "speaker": "SPEAKER_00",
             "text": "We should launch the beta in March."},
        ]
        result = analyze_transcript.invoke({"segments_json": str(segments)})
        assert "summary" in result
        assert "decisions" in result
        assert "participants" in result

def test_extract_action_items():
    with patch("src.agent.tools.get_llm", return_value=make_mock_llm(FAKE_ACTIONS)):
        from src.agent.tools import extract_action_items
        segments = [{"start": 0.0, "end": 4.0, "speaker": "SPEAKER_00",
                      "text": "I'll prepare the demo by Friday."}]
        result = extract_action_items.invoke({"segments_json": str(segments)})
        assert "action_items" in result
        assert result["action_items"][0]["owner"] == "SPEAKER_00"

def test_generate_report():
    from src.db.sqlite import Database
    db = Database(":memory:")
    with patch("src.agent.tools.get_llm", return_value=make_mock_llm(FAKE_REPORT)):
        from src.agent.tools import generate_report
        result = generate_report.invoke({
            "meeting_id": "m-001",
            "meeting_title": "Sprint Planning",
            "meeting_date": "2026-03-24",
            "summary": "Team agreed to launch beta.",
            "decisions_json": '["Launch beta in March"]',
            "action_items_json": '[{"task":"Prepare demo","owner":"SPEAKER_00","due_date":"Friday","status":"pending"}]',
            "segments_json": "[]",
            "db_path": ":memory:",
        })
        assert "report_markdown" in result
        assert "Sprint Planning" in result["report_markdown"]

def test_search_meetings():
    from src.db.vector_store import VectorStore
    store = VectorStore(ephemeral=True)
    store.index_segments(
        meeting_id="m-001",
        meeting_title="Sprint Planning",
        date="2026-03-24",
        segments=[{"start": 0.0, "end": 4.0, "speaker": "SPEAKER_00",
                   "text": "We will prepare the demo by Friday."}],
    )
    with patch("src.agent.tools.VectorStore", return_value=store):
        from src.agent.tools import search_meetings
        result = search_meetings.invoke({"query": "demo preparation", "top_k": 1})
        assert "results" in result
        assert len(result["results"]) == 1
        assert result["results"][0]["speaker"] == "SPEAKER_00"
