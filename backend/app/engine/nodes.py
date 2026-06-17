"""Graph node factories. Each returns a callable closed over a resolved AgentDef.

Nodes:
  select → choose the best skill for the request (suppressed from the token stream)
  agent  → LLM bound to (agent tools ∪ selected skill's required tools)
  tools  → execute tool calls via the ToolRegistry adapters
"""

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from ..registries.skill_registry import SKILL_REGISTRY
from ..registries.tool_registry import TOOL_REGISTRY
from ..registries.types import AgentDef
from .context import assemble_system_prompt
from .llm import get_llm
from .state import AgentState

_SELECT_PROMPT = """Classify the user's request into exactly one of the skills below.
Reply with ONLY the skill slug.

Skills:
{skills}

User request: {request}"""


def _auto_recall(agent: AgentDef, last_human) -> list[str]:
    """Recall long-term memories for the request when the agent opts in (config
    auto_recall) or carries the recall_memory tool. Off by default to control cost."""
    from ..core.db import db_enabled

    if last_human is None or not db_enabled():
        return []
    wants = agent.config.get("auto_recall") or ("recall_memory" in agent.tools)
    if not wants:
        return []
    try:
        from ..memory import store

        return store.recall(last_human.content, k=3, namespace=agent.slug)
    except Exception:
        return []


def make_select_node(agent: AgentDef):
    skills = SKILL_REGISTRY.get_many(agent.skills)

    def select(state: AgentState) -> dict:
        last_human = next(
            (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
            None,
        )
        recalled = _auto_recall(agent, last_human)

        if not skills:
            return {"selected_skill": None, "recalled": recalled}
        if len(skills) == 1 or last_human is None:
            return {"selected_skill": skills[0].slug, "recalled": recalled}

        catalog = "\n".join(f"- {s.slug}: {s.when_to_use}" for s in skills)
        chosen = skills[0].slug
        try:
            llm = get_llm(streaming=False, model=agent.model)
            resp = llm.invoke(
                [HumanMessage(content=_SELECT_PROMPT.format(skills=catalog, request=last_human.content))]
            )
            answer = resp.content.strip().lower()
            for s in skills:
                if s.slug in answer:
                    chosen = s.slug
                    break
        except Exception:
            pass
        return {"selected_skill": chosen, "recalled": recalled}

    return select


def _tool_slugs_for(agent: AgentDef, selected_skill: str | None) -> list[str]:
    slugs = list(agent.tools)
    if selected_skill:
        try:
            skill = SKILL_REGISTRY.get(selected_skill)
            for t in skill.required_tools:
                if t not in slugs:
                    slugs.append(t)
        except KeyError:
            pass
    return slugs


def make_agent_node(agent: AgentDef):
    def call_model(state: AgentState) -> dict:
        selected = state.get("selected_skill")
        # Capability scoping: bind only the agent's granted tools (+ skill's required).
        tools = TOOL_REGISTRY.resolve(_tool_slugs_for(agent, selected))
        llm = get_llm(model=agent.model)
        llm = llm.bind_tools(tools) if tools else llm

        system = assemble_system_prompt(
            agent, selected, state.get("recalled"), state.get("plan")
        )
        messages = [SystemMessage(content=system)] + state["messages"]
        response = llm.invoke(messages)
        return {"messages": [response]}

    return call_model


def make_tools_node(agent: AgentDef):
    def call_tools(state: AgentState) -> dict:
        last = state["messages"][-1]
        results = []
        for tool_call in last.tool_calls:
            try:
                tool = TOOL_REGISTRY.get_langchain_tool(tool_call["name"])
                result = tool.invoke(tool_call["args"])
            except Exception as e:
                result = f"Tool error: {e}"
            results.append(
                ToolMessage(content=str(result), tool_call_id=tool_call["id"])
            )
        return {"messages": results}

    return call_tools
