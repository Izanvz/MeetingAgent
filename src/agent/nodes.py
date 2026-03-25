import json

from src.agent.state import MeetingAgentState
from src.agent.tools import analyze_transcript, extract_action_items, generate_report


def node_analyze(state: MeetingAgentState) -> dict:
    """Step 1: summarise the transcript and extract decisions."""
    segments_json = json.dumps(state["transcript_segments"])
    result = analyze_transcript.invoke({"segments_json": segments_json})
    return {
        "summary": result.get("summary", ""),
        "decisions": result.get("decisions", []),
    }


def node_extract(state: MeetingAgentState) -> dict:
    """Step 2: extract action items with owners and deadlines."""
    segments_json = json.dumps(state["transcript_segments"])
    result = extract_action_items.invoke({"segments_json": segments_json})
    return {"action_items": result.get("action_items", [])}


def node_report(state: MeetingAgentState) -> dict:
    """Step 3: generate markdown report and persist to SQLite."""
    result = generate_report.invoke({
        "meeting_id": state["meeting_id"],
        "meeting_title": state["meeting_title"],
        "meeting_date": state["meeting_date"],
        "summary": state["summary"],
        "decisions_json": json.dumps(state["decisions"]),
        "action_items_json": json.dumps(state["action_items"]),
        "segments_json": json.dumps(state["transcript_segments"]),
    })
    return {"report_markdown": result.get("report_markdown", "")}
