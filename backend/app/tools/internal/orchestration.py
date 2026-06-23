"""Multi-agent orchestration — agent-as-tool handoff.

`delegate_to_agent` lets an orchestrator agent invoke another agent's compiled graph
synchronously and use its final answer, enabling hierarchical multi-agent flows.
"""

import re

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool

from ...registries.tool_registry import register_tool

# Markers a sub-agent's tools emit for downloads / live previews. The top-level runner
# (run_agent_stream) only scans this tool's OWN output, so we must re-surface any markers
# produced inside the delegated sub-graph or the UI never sees the artifact/preview.
_MARKER_RE = re.compile(r"(ARTIFACT:\{.*?\}|PREVIEW_URL: https://\S+)")


def _collect_markers(messages) -> list[str]:
    seen: list[str] = []
    for msg in messages:
        content = getattr(msg, "content", "")
        if not isinstance(content, str):
            continue
        for m in _MARKER_RE.findall(content):
            if m not in seen:
                seen.append(m)
    return seen


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

    messages = result.get("messages", [])
    # Re-surface artifact/preview markers so the parent run's scanner emits them to the UI.
    markers = _collect_markers(messages)
    suffix = ("\n\n" + "\n".join(markers)) if markers else ""

    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            return f"[{agent_slug}] {msg.content}{suffix}"
    return f"[{agent_slug}] completed with no textual response.{suffix}"
