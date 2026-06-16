"""Per-agent graph builder. Generalizes the original `build_graph()` so the graph
is data-driven by an AgentDef instead of a single hardcoded agent.

Shape: select → agent ⇄ tools (loop until no tool calls).
"""

from langgraph.graph import END, StateGraph

from ..registries.types import AgentDef
from .nodes import make_agent_node, make_select_node, make_tools_node
from .state import AgentState


def build_agent_graph(agent: AgentDef):
    select = make_select_node(agent)
    call_model = make_agent_node(agent)
    call_tools = make_tools_node(agent)

    def should_continue(state: AgentState) -> str:
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return END

    graph = StateGraph(AgentState)
    graph.add_node("select", select)
    graph.add_node("agent", call_model)
    graph.add_node("tools", call_tools)
    graph.set_entry_point("select")
    graph.add_edge("select", "agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()
