"""Response schemas for the workflows feature."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.features.workflows.models import WorkflowRunStatus


class GraphSpecRead(BaseModel):
    """The executable graph specification of one version."""

    topology: str
    agents: list[str]
    fallback_agent: str
    approval_gate: bool


class WorkflowVersionRead(BaseModel):
    """One immutable version of a definition."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    definition_id: UUID
    version: int
    graph_spec: dict[str, Any]
    is_active: bool
    notes: str
    created_at: datetime


class WorkflowDefinitionRead(BaseModel):
    """A named workflow."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str
    cloned_from_id: UUID | None
    created_at: datetime


class WorkflowDefinitionDetailRead(BaseModel):
    """A definition with its full version history."""

    definition: WorkflowDefinitionRead
    versions: list[WorkflowVersionRead]
    active_version: WorkflowVersionRead | None


class WorkflowDefinitionCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    graph_spec: dict[str, Any]


class WorkflowVersionCreateRequest(BaseModel):
    graph_spec: dict[str, Any]
    notes: str = Field(default="", max_length=500)
    # Adding a version without activating it is how a change is staged for
    # review; the default matches the common case of shipping it immediately.
    activate: bool = True


class WorkflowCloneRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class AgentCatalogueRead(BaseModel):
    """Agents a graph_spec may reference on this deployment."""

    agents: list[str]


class WorkflowRunRead(BaseModel):
    """A workflow run summary."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workflow_name: str
    # The exact version that produced this run; null for runs recorded before
    # versioning existed.
    workflow_version_id: UUID | None = None
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
