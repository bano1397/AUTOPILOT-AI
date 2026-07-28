"""add emails

One row per ingested message: the classification, extracted entities, drafted
reply, and the human send/discard decision. `message_id` is unique so re-syncing
a mailbox cannot duplicate a message.

Revision ID: f2b46e8c31da
Revises: e5c1a7d24b83
Create Date: 2026-07-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2b46e8c31da"
down_revision: str | None = "e5c1a7d24b83"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INTENTS = (
    "question",
    "request",
    "complaint",
    "meeting",
    "invoice",
    "sales",
    "support",
    "spam",
    "other",
)
_STATUSES = (
    "received",
    "processing",
    "awaiting_approval",
    "sent",
    "discarded",
    "failed",
)


def upgrade() -> None:
    op.create_table(
        "emails",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("uid", sa.String(length=100), nullable=False),
        sa.Column("message_id", sa.String(length=500), nullable=False),
        sa.Column("sender", sa.String(length=500), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("intent", sa.Enum(*_INTENTS, name="email_intent"), nullable=True),
        sa.Column("entities", sa.JSON(), nullable=False),
        sa.Column("status", sa.Enum(*_STATUSES, name="email_status"), nullable=False),
        sa.Column("draft", sa.Text(), nullable=True),
        sa.Column("grounded", sa.Boolean(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("fk_emails_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_emails")),
    )
    op.create_index("ix_emails_user_id", "emails", ["user_id"])
    op.create_index("ix_emails_status", "emails", ["status"])
    op.create_index("ix_emails_message_id", "emails", ["message_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_emails_message_id", table_name="emails")
    op.drop_index("ix_emails_status", table_name="emails")
    op.drop_index("ix_emails_user_id", table_name="emails")
    op.drop_table("emails")
    sa.Enum(name="email_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="email_intent").drop(op.get_bind(), checkfirst=True)
