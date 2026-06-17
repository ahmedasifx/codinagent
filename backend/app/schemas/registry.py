"""Request/response DTOs for the registry CRUD endpoints (tools, credentials,
MCP servers, agents, skills)."""

from typing import Any

from pydantic import BaseModel, Field


# ── Tools ──
class ToolIn(BaseModel):
    slug: str
    name: str
    description: str = ""
    type: str = "rest_api"  # internal | rest_api | mcp | external | ...
    spec: dict[str, Any] = Field(default_factory=dict)
    credential_id: str | None = None


class ToolUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    spec: dict[str, Any] | None = None
    credential_id: str | None = None


class ToolOut(BaseModel):
    id: str | None = None
    slug: str
    name: str = ""
    description: str = ""
    type: str = "internal"
    spec: dict[str, Any] = Field(default_factory=dict)
    is_core: bool = False


class ToolTestIn(BaseModel):
    args: dict[str, Any] = Field(default_factory=dict)


# ── Credentials ──
class CredentialIn(BaseModel):
    name: str
    type: str = "bearer"  # bearer | api_key | basic | oauth
    secret_ref: str  # env var name / secret-manager key — NOT the raw secret


class CredentialOut(BaseModel):
    id: str
    name: str
    type: str
    secret_ref: str


# ── MCP ──
class McpServerIn(BaseModel):
    slug: str
    name: str = ""
    description: str = ""
    connection: dict[str, Any]  # {transport, command/url, args, ...}
    tool_name: str | None = None  # expose a single tool from the server (optional)


# ── Skills ──
class SkillIn(BaseModel):
    slug: str
    name: str
    description: str = ""
    instructions: str = ""
    when_to_use: str = ""
    required_tools: list[str] = Field(default_factory=list)
    sub_skills: list[str] = Field(default_factory=list)


class SkillOut(BaseModel):
    id: str | None = None
    slug: str
    name: str = ""
    description: str = ""
    when_to_use: str = ""
    required_tools: list[str] = Field(default_factory=list)
    is_core: bool = False


# ── Agents ──
class AgentIn(BaseModel):
    slug: str
    name: str
    description: str = ""
    instructions: str = ""
    personality: str = ""
    system_prompt: str = ""
    model: str | None = None
    skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    instructions: str | None = None
    personality: str | None = None
    system_prompt: str | None = None
    model: str | None = None
    skills: list[str] | None = None
    tools: list[str] | None = None
    config: dict[str, Any] | None = None


class AgentOut(BaseModel):
    id: str | None = None
    slug: str
    name: str
    description: str = ""
    skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    is_core: bool = False
