"""add calendar events

Storage for the local calendar provider (blueprint §5, provider #10). Only that
adapter reads this table — the Google adapter has no rows.

Revision ID: d4a71e9b3c86
Revises: c9f207b4e18a
Create Date: 2026-07-31
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4a71e9b3c86"
down_revision: str | None = "c9f207b4e18a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "calendar_events",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("location", sa.String(length=300), nullable=False),
        sa.Column("attendees", sa.JSON(), nullable=False),
        sa.Column("external_id", sa.String(length=200), nullable=True),
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
            name=op.f("fk_calendar_events_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_calendar_events")),
    )
    op.create_index(
        op.f("ix_calendar_events_user_id"), "calendar_events", ["user_id"], unique=False
    )
    # Every read is a range scan over the start time.
    op.create_index(
        op.f("ix_calendar_events_starts_at"),
        "calendar_events",
        ["starts_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_calendar_events_starts_at"), table_name="calendar_events")
    op.drop_index(op.f("ix_calendar_events_user_id"), table_name="calendar_events")
    op.drop_table("calendar_events")
