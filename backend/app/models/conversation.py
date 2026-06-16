"""Conversation, message, and run (one agent turn) tables."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from .base import OwnedMixin, TimestampMixin, UUIDPK


class Conversation(UUIDPK, OwnedMixin, TimestampMixin, Base):
    __tablename__ = "conversations"

    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id"), nullable=True
    )
    agent_slug: Mapped[str] = mapped_column(String(128))
    title: Mapped[str] = mapped_column(String(512), default="")


class Message(UUIDPK, TimestampMixin, Base):
    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))  # user | assistant | tool | system
    content: Mapped[str] = mapped_column(Text, default="")
    tool_calls: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tool_call_id: Mapped[str | None] = mapped_column(String(128), nullable=True)


class Run(UUIDPK, TimestampMixin, Base):
    __tablename__ = "runs"

    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True
    )
    agent_slug: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), default="running")  # running|done|error
    selected_skill: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
