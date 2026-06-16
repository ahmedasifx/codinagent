"""Code-defined domain types held by the registries (independent of the ORM)."""

from dataclasses import dataclass, field


@dataclass
class SkillDef:
    slug: str
    name: str
    description: str
    instructions: str
    when_to_use: str
    required_tools: list[str] = field(default_factory=list)  # tool slugs
    sub_skills: list[str] = field(default_factory=list)  # skill slugs (composition)
    is_core: bool = True


@dataclass
class AgentDef:
    slug: str
    name: str
    description: str
    instructions: str = ""
    personality: str = ""
    system_prompt: str = ""
    model: str | None = None
    skills: list[str] = field(default_factory=list)  # skill slugs
    tools: list[str] = field(default_factory=list)  # always-on tool slugs
    is_core: bool = True
