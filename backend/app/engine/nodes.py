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


def make_select_node(agent: AgentDef):
    skills = SKILL_REGISTRY.get_many(agent.skills)

    def select(state: AgentState) -> dict:
        if not skills:
            return {"selected_skill": None}
        if len(skills) == 1:
            return {"selected_skill": skills[0].slug}

        last_human = next(
            (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
            None,
        )
        if last_human is None:
            return {"selected_skill": skills[0].slug}

        catalog = "\n".join(f"- {s.slug}: {s.when_to_use}" for s in skills)
        try:
            llm = get_llm(streaming=False, model=agent.model)
            resp = llm.invoke(
                [
                    HumanMessage(
                        content=_SELECT_PROMPT.format(
                            skills=catalog, request=last_human.content
                        )
                    )
                ]
            )
            answer = resp.content.strip().lower()
            for s in skills:
                if s.slug in answer:
                    return {"selected_skill": s.slug}
        except Exception:
            pass
        return {"selected_skill": skills[0].slug}

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

        system = assemble_system_prompt(agent, selected, state.get("recalled"))
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
