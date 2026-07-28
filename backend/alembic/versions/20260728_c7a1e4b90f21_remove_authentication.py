"""remove authentication

Authentication is removed from the platform (docs/COMPLETION_PLAN.md §3): the
app is a single shared workspace. This migration:

1. Renames the existing shared identity to a non-reserved domain. ``.local`` is
   an IANA special-use TLD that ``EmailStr`` rejects, which made every response
   carrying the user 500.
2. Drops ``refresh_tokens`` — no tokens are issued any more.
3. Drops ``users.password_hash`` and ``users.role`` — nothing authenticates and
   nothing authorizes, so both columns were misleading dead data.

``users`` itself is kept: every feature's ``user_id`` foreign key and the
vector-store metadata filter point at it.

Revision ID: c7a1e4b90f21
Revises: 40ffe622148c
Create Date: 2026-07-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7a1e4b90f21"
down_revision: str | None = "40ffe622148c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_EMAIL = "public@autopilot.local"
_NEW_EMAIL = "workspace@autopilot.dev"


def upgrade() -> None:
    # Heal already-deployed instances before the column set changes.
    op.execute(
        sa.text("UPDATE users SET email = :new WHERE email = :old").bindparams(
            new=_NEW_EMAIL, old=_OLD_EMAIL
        )
    )

    # Dropping the table takes its indexes with it on both SQLite and Postgres.
    op.drop_table("refresh_tokens")

    # Batch mode so SQLite (which rebuilds the table) works as well as Postgres.
    with op.batch_alter_table("users") as batch:
        batch.drop_column("password_hash")
        batch.drop_column("role")

    # Postgres keeps the enum type after its last column is dropped.
    sa.Enum(name="user_role").drop(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    sa.Enum("admin", "user", name="user_role").create(op.get_bind(), checkfirst=True)

    # Server defaults let the columns come back NOT NULL over existing rows;
    # the placeholder hash is deliberately non-verifiable.
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column(
                "password_hash",
                sa.String(length=255),
                nullable=False,
                server_default="!disabled",
            )
        )
        batch.add_column(
            sa.Column(
                "role",
                sa.Enum("admin", "user", name="user_role"),
                nullable=False,
                server_default="user",
            )
        )

    op.create_table(
        "refresh_tokens",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("jti", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
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
            name=op.f("fk_refresh_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
    )
    op.create_index("ix_refresh_tokens_jti", "refresh_tokens", ["jti"], unique=True)
    op.create_index(
        "ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"], unique=False
    )

    op.execute(
        sa.text("UPDATE users SET email = :old WHERE email = :new").bindparams(
            new=_NEW_EMAIL, old=_OLD_EMAIL
        )
    )
