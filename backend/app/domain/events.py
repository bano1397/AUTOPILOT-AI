"""Domain event catalog.

Events are immutable value objects published on the :class:`EventBus`. Producers
emit them without knowledge of consumers, keeping the system decoupled. Concrete
events gain fields as their producing features are implemented; the base contract
and the canonical set of event types are defined here from the outset.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class DomainEvent(BaseModel):
    """Base class for all domain events."""

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def name(self) -> str:
        """Human-readable event name (the concrete class name)."""
        return type(self).__name__


# --- Workflow lifecycle -----------------------------------------------------
class WorkflowStarted(DomainEvent):
    run_id: str
    workflow_name: str
    user_id: str


class WorkflowStepCompleted(DomainEvent):
    run_id: str
    node_name: str
    duration_ms: int


class WorkflowCompleted(DomainEvent):
    run_id: str


class WorkflowFailed(DomainEvent):
    run_id: str
    error: str


# --- Documents & knowledge --------------------------------------------------
class DocumentUploaded(DomainEvent):
    document_id: str
    user_id: str


class DocumentReindexRequested(DomainEvent):
    """Re-run ingestion for an already-stored document.

    Separate from :class:`DocumentUploaded` because the handler must first tear
    down the previous chunks and vectors; conflating the two would make an
    ordinary upload capable of deleting an indexed document's data.
    """

    document_id: str
    user_id: str


class DocumentIndexed(DomainEvent):
    document_id: str
    chunk_count: int


# --- Agents -----------------------------------------------------------------
class ResearchCompleted(DomainEvent):
    run_id: str
    topic: str


class EmailDrafted(DomainEvent):
    run_id: str
    email_id: str


# --- Human-in-the-loop ------------------------------------------------------
class ApprovalRequired(DomainEvent):
    run_id: str
    approval_id: str
    action_type: str


class ApprovalReceived(DomainEvent):
    run_id: str
    approval_id: str
    decision: str


# --- Cross-cutting ----------------------------------------------------------
class NotificationRequested(DomainEvent):
    user_id: str
    channel: str
    message: str


class MemoryWritten(DomainEvent):
    user_id: str
    level: str


class CostRecorded(DomainEvent):
    execution_id: str
    provider: str
    model: str
    cost_usd: float
