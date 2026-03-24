from langgraph.graph import StateGraph, START

from src.agent.state import MeetingAgentState
from src.agent.nodes import agent_node, tool_node, should_continue


def build_graph():
    builder = StateGraph(MeetingAgentState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tool_node)
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", should_continue, {"tools": "tools", "__end__": "__end__"})
    builder.add_edge("tools", "agent")
    return builder.compile()
