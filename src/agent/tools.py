import json
import os
import uuid

from langchain_core.tools import tool

from src.db.sqlite import Database
from src.db.vector_store import VectorStore
from src.providers.llm import get_llm


@tool
def analyze_transcript(segments_json: str) -> dict:
    """Analyze a WhisperX transcript. Input: JSON string of segment list.
    Returns dict with summary, decisions, participants."""
    llm = get_llm()
    prompt = f"""You are analyzing a meeting transcript. Each segment has speaker, start, end, and text.

Transcript segments:
{segments_json}

Return a JSON object with:
- summary: 2-3 sentence summary of the meeting
- decisions: list of key decisions made
- participants: list of unique speaker IDs

Respond ONLY with valid JSON."""
    response = llm.invoke(prompt)
    content = response.content.strip().removeprefix("```json").removesuffix("```").strip()
    return json.loads(content)


@tool
def extract_action_items(segments_json: str) -> dict:
    """Extract action items from transcript segments.
    Returns dict with action_items list (task, owner, due_date, status)."""
    llm = get_llm()
    prompt = f"""Extract all action items from this meeting transcript.

Transcript segments:
{segments_json}

Return a JSON object with:
- action_items: list of objects, each with:
  - task: clear description of what needs to be done
  - owner: speaker ID who is responsible (e.g. "SPEAKER_00")
  - due_date: deadline if mentioned, else null
  - status: always "pending"

Respond ONLY with valid JSON."""
    response = llm.invoke(prompt)
    content = response.content.strip().removeprefix("```json").removesuffix("```").strip()
    return json.loads(content)


@tool
def generate_report(
    meeting_id: str,
    meeting_title: str,
    meeting_date: str,
    summary: str,
    decisions_json: str,
    action_items_json: str,
    segments_json: str,
    db_path: str = "data/meetings.db",
) -> dict:
    """Generate a markdown report and persist meeting to SQLite.
    Returns dict with report_markdown."""
    decisions = json.loads(decisions_json)
    action_items = json.loads(action_items_json)
    segments = json.loads(segments_json)

    llm = get_llm()
    prompt = f"""Write a professional meeting report in markdown.

Title: {meeting_title}
Date: {meeting_date}
Summary: {summary}
Decisions: {decisions}
Action Items: {action_items}

Include sections: Summary, Key Decisions, Action Items (with checkboxes), Participants."""
    response = llm.invoke(prompt)
    report_md = response.content.strip()

    db = Database(db_path)
    speakers = list({seg.get("speaker", "") for seg in segments if seg.get("speaker")})
    duration_s = max((seg.get("end", 0) for seg in segments), default=None)

    db.create_meeting({
        "id": meeting_id,
        "title": meeting_title,
        "date": meeting_date,
        "duration_s": duration_s,
        "speakers": speakers,
        "decisions": decisions,
        "summary": summary,
        "report_md": report_md,
    })
    for item in action_items:
        db.create_action_item({
            "id": str(uuid.uuid4()),
            "meeting_id": meeting_id,
            **item,
        })

    return {"report_markdown": report_md}


@tool
def search_meetings(query: str, top_k: int = 5) -> dict:
    """Search past meeting transcripts using semantic similarity.
    Returns dict with results list (text, speaker, start, end, meeting_id, meeting_title, date)."""
    store = VectorStore(
        host=os.getenv("CHROMA_HOST", "localhost"),
        port=int(os.getenv("CHROMA_PORT", "8001")),
    )
    results = store.search(query=query, top_k=top_k)
    return {"results": results}
