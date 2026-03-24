from typing import TypedDict
from langchain_core.messages import BaseMessage


class ActionItem(TypedDict):
    task: str
    owner: str
    due_date: str
    status: str


class MeetingAgentState(TypedDict):
    # Input
    transcript_segments: list[dict]
    meeting_title: str
    meeting_date: str

    # Accumulated by tools
    messages: list[BaseMessage]
    summary: str
    decisions: list[str]
    action_items: list[ActionItem]
    report_markdown: str

    # Control
    meeting_id: str
    job_id: str
