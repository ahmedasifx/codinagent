"""ContextAssembler — builds the final system prompt for an agent turn.

Replaces the original ad-hoc `SYSTEM_PROMPT + WORKFLOW_PROMPTS.get(...)` concat.
Composes: base agent identity + personality + selected skill instructions +
recalled long-term memories. A token budget / summarization step is layered in P2.
"""

from ..registries.skill_registry import SKILL_REGISTRY
from ..registries.types import AgentDef


def assemble_system_prompt(
    agent: AgentDef,
    selected_skill: str | None,
    recalled: list[str] | None = None,
) -> str:
    parts: list[str] = []

    if agent.system_prompt:
        parts.append(agent.system_prompt)
    if agent.instructions:
        parts.append("## Instructions\n" + agent.instructions)
    if agent.personality:
        parts.append("## Personality\n" + agent.personality)

    if selected_skill:
        try:
            skill = SKILL_REGISTRY.get(selected_skill)
            parts.append(
                f"## Active skill: {skill.name}\n{skill.instructions}"
            )
        except KeyError:
            pass

    if recalled:
        joined = "\n".join(f"- {m}" for m in recalled)
        parts.append("## Relevant memory\n" + joined)

    return "\n\n".join(p for p in parts if p)
