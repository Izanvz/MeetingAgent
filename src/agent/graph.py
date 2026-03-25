from langgraph.graph import StateGraph, START, END

from src.agent.state import MeetingAgentState
from src.agent.nodes import node_analyze, node_extract, node_report


def build_graph():
    builder = StateGraph(MeetingAgentState)
    builder.add_node("analyze", node_analyze)
    builder.add_node("extract", node_extract)
    builder.add_node("report", node_report)
    builder.add_edge(START, "analyze")
    builder.add_edge("analyze", "extract")
    builder.add_edge("extract", "report")
    builder.add_edge("report", END)
    return builder.compile()
