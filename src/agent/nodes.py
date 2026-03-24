import json

from langchain_core.messages import SystemMessage
from langgraph.prebuilt import ToolNode

from src.agent.state import MeetingAgentState
from src.agent.tools import analyze_transcript, extract_action_items, generate_report, search_meetings
from src.providers.llm import get_llm

TOOLS = [analyze_transcript, extract_action_items, generate_report, search_meetings]

SYSTEM_PROMPT = """You are a meeting analysis assistant. You receive a meeting transcript in WhisperX format.

Your job:
1. Call analyze_transcript with the segments to get summary, decisions, and participants.
2. Call extract_action_items with the segments to get tasks with owners and deadlines.
3. Call generate_report to persist everything to the database and get the markdown report.

Call the tools in this order. Do not skip steps. After generate_report, you are done."""


def agent_node(state: MeetingAgentState) -> dict:
    llm = get_llm().bind_tools(TOOLS)
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    if not state["messages"]:
        messages.append({"role": "user", "content": json.dumps(state["transcript_segments"])})
    response = llm.invoke(messages)
    return {"messages": state["messages"] + [response]}


def should_continue(state: MeetingAgentState) -> str:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return "__end__"


tool_node = ToolNode(TOOLS)
