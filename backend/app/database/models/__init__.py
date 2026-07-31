"""Aggregated model imports.

Importing this package registers every ORM model on ``Base.metadata`` so that
Alembic autogeneration and ``create_all`` see the complete schema. New models
must be imported here as they are added.
"""

from app.database.base import Base
from app.features.approvals.models import Approval, ApprovalStatus
from app.features.calendar.models import CalendarEventRow
from app.features.conversations.models import Conversation, Message
from app.features.documents.models import Document, DocumentChunk, DocumentStatus
from app.features.emails.models import Email, EmailIntent, EmailStatus
from app.features.memory.models import MemoryEntry, MemoryKind
from app.features.notifications.models import Notification
from app.features.preferences.models import WorkspacePreferences
from app.features.tasks.models import Task, TaskPriority, TaskStatus
from app.features.users.models import User
from app.features.workflows.models import (
    WorkflowDefinition,
    WorkflowRun,
    WorkflowRunStatus,
    WorkflowStep,
    WorkflowVersion,
)
from app.platform.observability.models import AiExecution

__all__ = [
    "AiExecution",
    "Approval",
    "ApprovalStatus",
    "Base",
    "CalendarEventRow",
    "Conversation",
    "Document",
    "DocumentChunk",
    "DocumentStatus",
    "Email",
    "EmailIntent",
    "EmailStatus",
    "MemoryEntry",
    "MemoryKind",
    "Message",
    "Notification",
    "WorkspacePreferences",
    "Task",
    "TaskPriority",
    "TaskStatus",
    "User",
    "WorkflowDefinition",
    "WorkflowRun",
    "WorkflowRunStatus",
    "WorkflowStep",
    "WorkflowVersion",
]
