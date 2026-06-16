"""Registry tables: agents, skills, tools, their M:N links, and credentials."""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from .base import OwnedMixin, TimestampMixin, UUIDPK


class Agent(UUIDPK, OwnedMixin, TimestampMixin, Base):
    __tablename__ = "agents"

    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text, default="")
    instructions: Mapped[str] = mapped_column(Text, default="")
    personality: Mapped[str] = mapped_column(Text, default="")
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_core: Mapped[bool] = mapped_column(Boolean, default=False)


class Skill(UUIDPK, OwnedMixin, TimestampMixin, Base):
    __tablename__ = "skills"

    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text, default="")
    instructions: Mapped[str] = mapped_column(Text, default="")
    when_to_use: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(String(16), default="config")  # code | config
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_core: Mapped[bool] = mapped_column(Boolean, default=False)


class Tool(UUIDPK, OwnedMixin, TimestampMixin, Base):
    __tablename__ = "tools"

    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text, default="")
    # internal | rest_api | mcp | external | database | search | image_gen
    type: Mapped[str] = mapped_column(String(32))
    spec: Mapped[dict] = mapped_column(JSONB, default=dict)
    credential_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("credentials.id"), nullable=True
    )
    is_core: Mapped[bool] = mapped_column(Boolean, default=False)


class Credential(UUIDPK, OwnedMixin, TimestampMixin, Base):
    """Stores a *reference* to a secret (env var name / secret-manager key), never
    the raw value."""

    __tablename__ = "credentials"

    name: Mapped[str] = mapped_column(String(256))
    type: Mapped[str] = mapped_column(String(64))  # bearer | api_key | basic | oauth
    secret_ref: Mapped[str] = mapped_column(String(256))


class AgentSkill(Base):
    __tablename__ = "agent_skills"
    __table_args__ = (UniqueConstraint("agent_id", "skill_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE")
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE")
    )
    position: Mapped[int] = mapped_column(Integer, default=0)


class SkillTool(Base):
    __tablename__ = "skill_tools"
    __table_args__ = (UniqueConstraint("skill_id", "tool_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE")
    )
    tool_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tools.id", ondelete="CASCADE")
    )


class AgentTool(Base):
    __tablename__ = "agent_tools"
    __table_args__ = (UniqueConstraint("agent_id", "tool_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE")
    )
    tool_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tools.id", ondelete="CASCADE")
    )
