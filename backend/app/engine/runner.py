"""Streaming runner for the per-agent execution engine.

Consumes LangGraph `astream_events(version="v2")` and yields the SSE protocol
described in the plan. Generalizes the original `run_agent_stream`:
  - tokens are streamed only from the `agent` node (the `select` node, like the old
    router, must not leak tokens)
  - `workflow` is generalized to `skill_selected`
  - tool results are scanned for PREVIEW_URL: (live preview) and ARTIFACT: (download)
"""

import re
import uuid
from typing import AsyncIterator

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage

from ..core.config import get_settings
from ..core.observability import start_trace
from ..registries.agent_registry import AGENT_REGISTRY
from ..registries.loader import load_builtins

PREVIEW_URL_RE = re.compile(r"PREVIEW_URL: (https://\S+)")
ARTIFACT_RE = re.compile(r"ARTIFACT:(\{.*?\})")


def _rebuild_history(history: list[dict]) -> list[AnyMessage]:
    msgs: list[AnyMessage] = []
    for msg in history:
        if msg["role"] == "user":
            msgs.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            msgs.append(AIMessage(content=msg["content"]))
    return msgs


async def run_agent_stream(
    message: str,
    history: list[dict],
    agent_slug: str | None = None,
    planning: str | None = None,
    approved_plan: str | None = None,
    session_id: str | None = None,
) -> AsyncIterator[dict]:
    load_builtins()
    agent_slug = agent_slug or get_settings().default_agent

    try:
        agent_def = AGENT_REGISTRY.get(agent_slug)
        graph = AGENT_REGISTRY.compiled_graph(agent_slug)
    except KeyError:
        yield {"type": "error", "content": f"Unknown agent: {agent_slug}"}
        yield {"type": "done"}
        return

    yield {"type": "agent_selected", "agent": agent_slug}

    # ── Planning mode ──
    from .planner import generate_plan, resolve_planning_mode

    mode = resolve_planning_mode(planning, agent_def.config, approved_plan)
    plan_text = approved_plan
    if mode in ("auto", "approve"):
        try:
            plan_text = generate_plan(agent_def, message, history)
        except Exception as e:
            friendly = (
                "The model is rate-limited right now (HTTP 429). Please retry in a "
                "moment, or set OPENROUTER_MODEL / OPENROUTER_FALLBACK_MODELS to a less "
                "busy model."
                if "429" in str(e) or "rate" in str(e).lower()
                else f"Could not generate a plan: {e}"
            )
            if mode == "approve":
                # Can't approve a non-plan — surface a retryable error and stop.
                yield {"type": "error", "content": friendly}
                yield {"type": "done"}
                return
            # auto: degrade gracefully — proceed to execute without a plan.
            plan_text = None
        else:
            yield {"type": "plan", "plan": plan_text}
            if mode == "approve":
                # Pause: wait for the user to approve before any tool runs.
                yield {"type": "awaiting_approval"}
                yield {"type": "done"}
                return

    lc_messages = _rebuild_history(history)
    lc_messages.append(HumanMessage(content=message))

    initial = {
        "messages": lc_messages,
        "agent_slug": agent_slug,
        "selected_skill": None,
        "recalled": [],
        "plan": plan_text,  # off → None; auto/execute → the plan
    }

    try:
        # Default LangGraph recursion_limit (25 super-steps) is too low for long
        # multi-step agents (e.g. the infographic-video pipeline does ~15+ tool calls).
        trace_id, lf_handler = start_trace(
            session_id=session_id or str(uuid.uuid4()),
            agent_slug=agent_slug,
            name=f"{agent_slug}: {message[:80]}",
        )
        if trace_id:
            # Surface the trace id so the client can attach user feedback to this run.
            yield {"type": "trace", "trace_id": trace_id}
        config = {"recursion_limit": 150}
        if lf_handler:
            config["callbacks"] = [lf_handler]

        async for event in graph.astream_events(initial, version="v2", config=config):
            kind = event["event"]
            name = event.get("name", "")

            if kind == "on_chat_model_stream":
                if event.get("metadata", {}).get("langgraph_node") != "agent":
                    continue
                chunk = event["data"]["chunk"]
                if chunk.content:
                    yield {"type": "token", "content": chunk.content}

            elif kind == "on_chain_end" and name == "select":
                output = event["data"].get("output") or {}
                if isinstance(output, dict) and output.get("selected_skill"):
                    yield {"type": "skill_selected", "skill": output["selected_skill"]}

            elif kind == "on_tool_start":
                yield {
                    "type": "tool_call",
                    "name": name,
                    "args": event["data"].get("input", {}),
                }

            elif kind == "on_tool_end":
                output = str(event["data"].get("output", ""))
                yield {"type": "tool_result", "content": output}
                preview = PREVIEW_URL_RE.search(output)
                if preview:
                    yield {"type": "preview", "url": preview.group(1)}
                for m in ARTIFACT_RE.finditer(output):
                    import json

                    try:
                        meta = json.loads(m.group(1))
                        yield {"type": "artifact", **meta}
                    except Exception:
                        continue

        yield {"type": "done"}

    except Exception as e:
        yield {"type": "error", "content": str(e)}
