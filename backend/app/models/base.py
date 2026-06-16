"""Shared column mixins for all ORM models."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..core.config import get_settings


def _system_user() -> uuid.UUID:
    return uuid.UUID(get_settings().system_user_id)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class OwnedMixin:
    """owner_id is nullable + defaults to the single system user today; the column
    exists so multi-tenancy is a later switch, not a migration rewrite."""

    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, default=_system_user
    )
    visibility: Mapped[str] = mapped_column(String(16), default="private")


class UUIDPK:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
