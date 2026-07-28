"""add prompt provenance to ai_executions

Records which catalogued prompt (key + immutable version) produced each LLM call,
so any past generation can be traced to the exact prompt text that caused it
(blueprint §18). Nullable: rows written before the prompt registry existed have
no provenance to claim, and not every call must come from the catalog.

Revision ID: d3f8b25c9a17
Revises: c7a1e4b90f21
Create Date: 2026-07-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d3f8b25c9a17"
down_revision: str | None = "c7a1e4b90f21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("ai_executions") as batch:
        batch.add_column(sa.Column("prompt_key", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("prompt_version", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ai_executions") as batch:
        batch.drop_column("prompt_version")
        batch.drop_column("prompt_key")
