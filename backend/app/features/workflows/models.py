"""Workflow run and step ORM models."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.mixins import TimestampMixin, UUIDMixin


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
