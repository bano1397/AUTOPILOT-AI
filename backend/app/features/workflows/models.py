"""Workflow definition, version, run, and step ORM models.

A definition is a named workflow; a version is one immutable ``graph_spec``
under it. Runs pin the version they executed, so a trace stays reproducible
even after the definition has moved on (blueprint §20).
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.mixins import TimestampMixin, UUIDMixin


class WorkflowDefinition(UUIDMixin, TimestampMixin, Base):
    """A named workflow. Its behaviour lives in its versions, not here."""

    __tablename__ = "workflow_definitions"
    __table_args__ = (
        UniqueConstraint("name", name="uq_workflow_definitions_name"),
    )

    # Stable identifier used by callers (e.g. "agents.ask"). Renaming a
    # definition would orphan the runs that reference it by name, so this is
    # treated as immutable once created.
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    # Set when this definition was produced by cloning another, so a fork's
    # origin stays traceable. ondelete=SET NULL: deleting the parent must not
    # cascade into unrelated workflows.
    cloned_from_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflow_definitions.id", ondelete="SET NULL"), nullable=True
    )


class WorkflowVersion(UUIDMixin, TimestampMixin, Base):
    """One immutable graph specification under a definition.

    Versions are never edited: changing a workflow means adding a version, and
    rollback means activating an earlier one. That is what lets a run's
    ``graph_spec`` be trusted as the thing that actually executed.
    """

    __tablename__ = "workflow_versions"
    __table_args__ = (
        UniqueConstraint(
            "definition_id", "version", name="uq_workflow_versions_def_version"
        ),
    )

    definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_definitions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    # The executable spec — see app/workflows/spec.py. Compiled by the graph
    # builder, not merely recorded.
    graph_spec: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    # Exactly one active version per definition; enforced in the service, which
    # deactivates the incumbent in the same transaction. A partial unique index
    # would express it in the schema but is not portable across SQLite and
    # Postgres in the same DDL.
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str] = mapped_column(String(500), default="", nullable=False)


class WorkflowRunStatus(str, enum.Enum):
    """Lifecycle of a workflow run."""

    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"  # used by the HITL approval gate
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowRun(UUIDMixin, TimestampMixin, Base):
    """One execution of a workflow graph. ``created_at`` is the start time."""

    __tablename__ = "workflow_runs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    workflow_name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    # The exact version that produced this run. Nullable because runs recorded
    # before versioning existed have no version to point at, and inventing one
    # would misattribute their behaviour. ondelete=SET NULL keeps the run's
    # history readable even if a definition is later deleted.
    workflow_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflow_versions.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    status: Mapped[WorkflowRunStatus] = mapped_column(
        Enum(
            WorkflowRunStatus,
            name="workflow_run_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=WorkflowRunStatus.RUNNING,
        nullable=False,
    )
    input: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class WorkflowStep(UUIDMixin, TimestampMixin, Base):
    """One executed node within a workflow run."""

    __tablename__ = "workflow_steps"

    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    node_name: Mapped[str] = mapped_column(String(100), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
