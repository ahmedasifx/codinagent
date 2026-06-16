"""Long-term memory table (pgvector embeddings).

pgvector's SQLAlchemy type is imported lazily/guarded so the module still imports in
environments where the extension package isn't installed (DB-less mode, tooling)."""

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from .base import OwnedMixin, TimestampMixin, UUIDPK

EMBED_DIM = 1536

try:  # pragma: no cover - depends on optional dependency
    from pgvector.sqlalchemy import Vector

    _embedding_type = Vector(EMBED_DIM)
except Exception:  # pragma: no cover
    from sqlalchemy import JSON

    _embedding_type = JSON  # fallback so imports never fail


class Memory(UUIDPK, OwnedMixin, TimestampMixin, Base):
    __tablename__ = "memories"

    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id"), nullable=True
    )
    namespace: Mapped[str] = mapped_column(String(256), index=True, default="default")
    content: Mapped[str] = mapped_column(Text)
    embedding = mapped_column(_embedding_type, nullable=True)
    meta: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
