"""add workspace preferences

A single-row table holding instance-wide preferences (there are no accounts to
scope them to — docs/COMPLETION_PLAN.md §3). The row is created lazily on first
read, so no data migration is needed.

Revision ID: e5c1a7d24b83
Revises: d3f8b25c9a17
Create Date: 2026-07-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5c1a7d24b83"
down_revision: str | None = "d3f8b25c9a17"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspace_preferences",
        sa.Column("theme", sa.String(length=10), nullable=False),
        sa.Column("default_top_k", sa.Integer(), nullable=False),
        sa.Column("require_approval_by_default", sa.Boolean(), nullable=False),
        sa.Column("notifications_enabled", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspace_preferences")),
    )


def downgrade() -> None:
    op.drop_table("workspace_preferences")
