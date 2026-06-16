"""Artifact metadata table — generated outputs (image/pdf/video/html/audio)."""

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from .base import TimestampMixin, UUIDPK


class Artifact(UUIDPK, TimestampMixin, Base):
    __tablename__ = "artifacts"

    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id"), nullable=True
    )
    type: Mapped[str] = mapped_column(String(16))  # image|pdf|video|html|audio
    uri: Mapped[str] = mapped_column(String(1024))
    mime: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    meta: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
