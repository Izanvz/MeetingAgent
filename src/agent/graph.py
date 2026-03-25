from langgraph.graph import StateGraph, START, END

from src.agent.state import MeetingAgentState
from src.agent.nodes import node_analyze, node_extract, node_report, node_persist


def _should_persist(state: MeetingAgentState) -> str:
    """Skip persist if there is nothing to save."""
    if state.get("report_markdown") and state.get("meeting_id"):
        return "persist"
    return END


def build_graph():
    builder = StateGraph(MeetingAgentState)
    builder.add_node("analyze", node_analyze)
    builder.add_node("extract", node_extract)
    builder.add_node("report", node_report)
    builder.add_node("persist", node_persist)
    builder.add_edge(START, "analyze")
    builder.add_edge("analyze", "extract")
    builder.add_edge("extract", "report")
    builder.add_conditional_edges("report", _should_persist, {"persist": "persist", END: END})
    builder.add_edge("persist", END)
    return builder.compile()
