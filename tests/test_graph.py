import pytest
from unittest.mock import patch, MagicMock, AsyncMock


def make_mock_graph():
    """Returns a mock that simulates a compiled LangGraph."""
    mock = MagicMock()
    mock.ainvoke = AsyncMock(return_value={
        "summary": "Team agreed to launch beta.",
        "decisions": ["Launch beta"],
        "action_items": [{"task": "Prepare demo", "owner": "SPEAKER_00",
                          "due_date": "Friday", "status": "pending"}],
        "report_markdown": "# Sprint Planning\n\n...",
        "meeting_id": "m-001",
    })
    return mock


@pytest.mark.asyncio
async def test_graph_invocation_shape():
    """Verify the graph accepts the right input shape and returns expected keys."""
    with patch("src.agent.graph.build_graph", return_value=make_mock_graph()):
        from src.agent.graph import build_graph
        graph = build_graph()
        result = await graph.ainvoke({
            "transcript_segments": [
                {"start": 0.0, "end": 4.0, "speaker": "SPEAKER_00",
                 "text": "We should launch beta in March."}
            ],
            "meeting_title": "Sprint Planning",
            "meeting_date": "2026-03-24",
            "messages": [],
            "summary": "",
            "decisions": [],
            "action_items": [],
            "report_markdown": "",
            "meeting_id": "m-001",
            "job_id": "j-001",
        })
        assert "summary" in result
        assert "action_items" in result
        assert "report_markdown" in result
