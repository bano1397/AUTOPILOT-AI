"""Response schemas for the workflows feature."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.features.workflows.models import WorkflowRunStatus


class WorkflowRunRead(BaseModel):
    """A workflow run summary."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workflow_name: str
    status: WorkflowRunStatus
    error: str | None
    created_at: datetime
    ended_at: datetime | None
    duration_ms: int | None


class WorkflowStepRead(BaseModel):
    """One executed node within a run."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    position: int
    node_name: str
    duration_ms: int


class WorkflowRunDetailRead(BaseModel):
    """A run with its input/output payloads and steps."""

    run: WorkflowRunRead
    input: dict[str, Any] | None
    output: dict[str, Any] | None
    steps: list[WorkflowStepRead]
