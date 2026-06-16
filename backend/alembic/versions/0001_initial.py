"""initial schema (registries, conversations, memory, artifacts)

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-16

Uses Base.metadata for the first revision so the pgvector `Vector` column emits its
own DDL correctly. Subsequent migrations should be `--autogenerate`d.
"""

from typing import Sequence, Union

from alembic import op

from app.core.db import Base
import app.models  # noqa: F401  (populate Base.metadata)

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    bind = op.get_bind()
    Base.metadata.create_all(bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind)
