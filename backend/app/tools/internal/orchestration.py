"""Multi-agent orchestration — agent-as-tool handoff.

`delegate_to_agent` lets an orchestrator agent invoke another agent's compiled graph
synchronously and use its final answer, enabling hierarchical multi-agent flows.
"""

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool

from ...registries.tool_registry import register_tool


@register_tool
@tool
def delegate_to_agent(agent_slug: str, task: str) -> str:
    """Delegate a self-contained task to another agent and return its result.

    Use to hand off specialised work (e.g. agent_slug="infographic_video" to make a
    video, "document" for a PDF). Give a complete, standalone task description.
    """
    from ...registries.agent_registry import AGENT_REGISTRY

    try:
        graph = AGENT_REGISTRY.compiled_graph(agent_slug)
    except KeyError:
        return f"Unknown agent: {agent_slug}"

    state = {
        "messages": [HumanMessage(content=task)],
        "agent_slug": agent_slug,
        "selected_skill": None,
        "recalled": [],
    }
    try:
        result = graph.invoke(state, config={"recursion_limit": 150})
    except Exception as e:
        return f"Delegation to '{agent_slug}' failed: {e}"

    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, AIMessage) and msg.content:
            return f"[{agent_slug}] {msg.content}"
    return f"[{agent_slug}] completed with no textual response."
