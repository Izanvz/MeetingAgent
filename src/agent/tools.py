import json
import os
import re
import uuid
from functools import lru_cache

from langchain_core.tools import tool

from src.db.sqlite import Database
from src.db.vector_store import VectorStore
from src.providers.llm import get_llm


def _parse_json(text: str) -> dict:
    """Extract and parse JSON from LLM output, handling common quirks."""
    text = re.sub(r"```(?:json)?", "", text).strip()
    text = re.sub(r",\s*([\}\]])", r"\1", text)
    match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if match:
        text = match.group(1)
    return json.loads(text)


def _parse_json_safe(text: str, default: dict) -> dict:
    """Like _parse_json but returns default on failure instead of raising."""
    try:
        return _parse_json(text)
    except (json.JSONDecodeError, AttributeError):
        return default


@lru_cache(maxsize=1)
def get_vector_store() -> VectorStore:
    return VectorStore(
        host=os.getenv("CHROMA_HOST", "localhost"),
        port=int(os.getenv("CHROMA_PORT", "8001")),
    )


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
    return _parse_json_safe(response.content, {"summary": "", "decisions": [], "participants": []})


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
    return _parse_json_safe(response.content, {"action_items": []})


@tool
def generate_report(
    meeting_title: str,
    meeting_date: str,
    summary: str,
    decisions_json: str,
    action_items_json: str,
) -> dict:
    """Generate a markdown report from meeting data. Returns dict with report_markdown."""
    decisions = json.loads(decisions_json)
    action_items = json.loads(action_items_json)

    llm = get_llm()
    prompt = f"""Write a professional meeting report in markdown.

Title: {meeting_title}
Date: {meeting_date}
Summary: {summary}
Decisions: {decisions}
Action Items: {action_items}

Include sections: Summary, Key Decisions, Action Items (with checkboxes), Participants."""
    response = llm.invoke(prompt)
    return {"report_markdown": response.content.strip()}


@tool
def search_meetings(query: str, top_k: int = 5) -> dict:
    """Search past meeting transcripts using semantic similarity.
    Returns dict with results list (text, speaker, start, end, meeting_id, meeting_title, date)."""
    results = get_vector_store().search(query=query, top_k=top_k)
    return {"results": results}
