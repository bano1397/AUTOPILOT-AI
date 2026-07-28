"""add long-term memory entries

Level 3 of the memory architecture (blueprint §16). The vectors live in a
separate vector-store collection (MEMORY_COLLECTION), not in the database, so
there is nothing to migrate there — an existing deployment starts with an empty
memory namespace, created on first write.

Revision ID: a4d90c17e6b2
Revises: f2b46e8c31da
Create Date: 2026-07-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a4d90c17e6b2"
down_revision: str | None = "f2b46e8c31da"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "memory_entries",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("vector_id", sa.String(length=64), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_memory_entries_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memory_entries")),
    )
    op.create_index(
        op.f("ix_memory_entries_user_id"), "memory_entries", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_memory_entries_user_id"), table_name="memory_entries")
    op.drop_table("memory_entries")
