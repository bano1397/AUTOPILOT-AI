"""Aggregated model imports.

Importing this package registers every ORM model on ``Base.metadata`` so that
Alembic autogeneration and ``create_all`` see the complete schema. New models
must be imported here as they are added.
"""

from app.database.base import Base
from app.features.approvals.models import Approval, ApprovalStatus
from app.features.auth.models import RefreshToken
from app.features.conversations.models import Conversation, Message
from app.features.documents.models import Document, DocumentChunk, DocumentStatus
from app.features.notifications.models import Notification
from app.features.tasks.models import Task, TaskPriority, TaskStatus
from app.features.users.models import User, UserRole
from app.features.workflows.models import WorkflowRun, WorkflowRunStatus, WorkflowStep
from app.platform.observability.models import AiExecution

__all__ = [
    "AiExecution",
    "Approval",
    "ApprovalStatus",
    "Base",
    "Conversation",
    "Document",
    "DocumentChunk",
    "DocumentStatus",
    "Message",
    "Notification",
    "RefreshToken",
    "Task",
    "TaskPriority",
    "TaskStatus",
    "User",
    "UserRole",
    "WorkflowRun",
    "WorkflowRunStatus",
    "WorkflowStep",
]
