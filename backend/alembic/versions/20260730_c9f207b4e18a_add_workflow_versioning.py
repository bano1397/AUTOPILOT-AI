"""add workflow definitions and versions

Blueprint §20: a named definition owns immutable versions, each holding an
executable ``graph_spec``; runs pin the version that produced them.

``workflow_runs.workflow_version_id`` is nullable with no backfill. Runs
recorded before versioning have no version to point at, and attaching them to
the seeded v1 would claim they executed a spec that did not exist when they
ran — the opposite of what pinning is for. They keep their ``workflow_name``
and read as unversioned history.

The seed definition itself is created lazily at startup rather than here, so
the migration stays pure DDL and does not need to know the agent registry.

Revision ID: c9f207b4e18a
Revises: b8e3f1c05a72
Create Date: 2026-07-30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9f207b4e18a"
down_revision: str | None = "b8e3f1c05a72"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflow_definitions",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("cloned_from_id", sa.Uuid(), nullable=True),
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
            ["cloned_from_id"],
            ["workflow_definitions.id"],
            name=op.f("fk_workflow_definitions_cloned_from_id_workflow_definitions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_definitions")),
        sa.UniqueConstraint("name", name="uq_workflow_definitions_name"),
    )

    op.create_table(
        "workflow_versions",
        sa.Column("definition_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("graph_spec", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=False),
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
            ["definition_id"],
            ["workflow_definitions.id"],
            name=op.f("fk_workflow_versions_definition_id_workflow_definitions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_versions")),
        sa.UniqueConstraint(
            "definition_id", "version", name="uq_workflow_versions_def_version"
        ),
    )
    op.create_index(
        op.f("ix_workflow_versions_definition_id"),
        "workflow_versions",
        ["definition_id"],
        unique=False,
    )

    # SQLite cannot ADD COLUMN with a foreign key, so the constraint is created
    # inside a batch (table-rebuild) operation. This is a no-op wrapper on
    # Postgres, which alters in place.
    with op.batch_alter_table("workflow_runs") as batch:
        batch.add_column(sa.Column("workflow_version_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_workflow_runs_workflow_version_id_workflow_versions",
            "workflow_versions",
            ["workflow_version_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index(
        op.f("ix_workflow_runs_workflow_version_id"),
        "workflow_runs",
        ["workflow_version_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_workflow_runs_workflow_version_id"), table_name="workflow_runs"
    )
    with op.batch_alter_table("workflow_runs") as batch:
        batch.drop_constraint(
            "fk_workflow_runs_workflow_version_id_workflow_versions",
            type_="foreignkey",
        )
        batch.drop_column("workflow_version_id")

    op.drop_index(
        op.f("ix_workflow_versions_definition_id"), table_name="workflow_versions"
    )
    op.drop_table("workflow_versions")
    op.drop_table("workflow_definitions")
