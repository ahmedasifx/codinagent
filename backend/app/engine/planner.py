"""Planning mode — generate a step-by-step plan before execution.

The plan is produced by a standalone non-streaming LLM call (so its tokens never leak
into the execution stream) and is either auto-executed or approved by the user first.
"""

import time

from langchain_core.messages import HumanMessage, SystemMessage

from ..registries.skill_registry import SKILL_REGISTRY
from ..registries.types import AgentDef
from .llm import get_llm


def _is_transient(err: Exception) -> bool:
    s = str(err).lower()
    return (
        "429" in s
        or "rate limit" in s
        or "rate-limit" in s
        or "provider returned error" in s
        or "overloaded" in s
        or "timeout" in s
    )


def _invoke_with_retry(llm, messages, attempts: int = 4):
    """Invoke the LLM, retrying transient errors (429 / provider hiccups) with backoff.
    Non-transient errors raise immediately; the last attempt's error propagates."""
    delay = 0.8
    for i in range(attempts):
        try:
            return llm.invoke(messages)
        except Exception as e:
            if i == attempts - 1 or not _is_transient(e):
                raise
            time.sleep(delay)
            delay *= 2

_PLAN_SYSTEM = """You are the planning step of an AI agent. Given the agent's role and
the user's request, produce a SHORT, concrete, numbered plan of the steps the agent will
take (use the agent's tools/skills). 4–8 steps, one line each. Output ONLY the numbered
list — no preamble, no explanation."""


def _skill_context(agent: AgentDef) -> str:
    skills = SKILL_REGISTRY.get_many(agent.skills)
    if not skills:
        return ""
    if len(skills) == 1:
        return f"\n\nActive skill — {skills[0].name}:\n{skills[0].instructions}"
    return "\n\nAvailable skills:\n" + "\n".join(
        f"- {s.name}: {s.when_to_use}" for s in skills
    )


def generate_plan(agent: AgentDef, message: str, history: list[dict] | None = None) -> str:
    """Return a concise numbered plan for the request (markdown).

    Raises on failure (after retrying transient errors) — callers decide how to handle
    it; a failed plan must never be presented to the user as an approvable plan.
    """
    role = agent.system_prompt or agent.instructions or f"You are {agent.name}."
    context = (
        f"Agent role:\n{role}{_skill_context(agent)}\n\n"
        f"Available tools: {', '.join(agent.tools) or '(none)'}"
    )
    llm = get_llm(streaming=False, model=agent.model)
    resp = _invoke_with_retry(llm, [
        SystemMessage(content=_PLAN_SYSTEM),
        HumanMessage(content=f"{context}\n\nUser request:\n{message}\n\nPlan:"),
    ])
    return resp.content.strip()


def resolve_planning_mode(
    request_planning: str | None,
    agent_config: dict | None,
    approved_plan: str | None,
) -> str:
    """Effective mode: off | auto | approve | execute.

    - an approved_plan always means we're in the execute (post-approval) phase
    - else an explicit request value wins
    - else the agent's configured default
    - else off
    """
    if approved_plan:
        return "execute"
    if request_planning in ("off", "auto", "approve"):
        return request_planning
    default = (agent_config or {}).get("planning", "off")
    return default if default in ("off", "auto", "approve") else "off"
