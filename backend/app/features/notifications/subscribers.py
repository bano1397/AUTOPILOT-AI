"""Event-bus subscribers that turn domain events into notifications.

Producers never know about notifications: this module subscribes to events the
platform already publishes. Events carry ids, not owners, so handlers resolve
the owning user from the database (the single source of truth).
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from app.core.config import get_settings
from app.core.logging import get_logger
from app.domain.events import (
    ApprovalRequired,
    DocumentIndexed,
    DomainEvent,
    WorkflowFailed,
)
from app.domain.interfaces.database import DatabaseProvider
from app.domain.interfaces.event_bus import EventBus
from app.features.documents.models import Document
from app.features.notifications.dispatcher import NotificationDispatcher
from app.features.workflows.models import WorkflowRun
from app.infrastructure.notifications import build_notification_providers

logger = get_logger("app.notifications.subscribers")


def register_notification_subscribers(
    bus: EventBus, resolve_db: Callable[[], DatabaseProvider]
) -> None:
    """Subscribe the notification handlers; resolves state at event time."""

    def dispatcher(db: DatabaseProvider) -> NotificationDispatcher:
        return NotificationDispatcher(
            db, build_notification_providers(get_settings(), db)
        )

    async def on_approval_required(event: DomainEvent) -> None:
        if not isinstance(event, ApprovalRequired):
            return
        db = resolve_db()
        user_id = await _run_owner(db, UUID(event.run_id))
        if user_id:
            await dispatcher(db).dispatch(
                user_id,
                kind="approval_required",
                title="Approval required",
                body="A drafted answer is awaiting your review on the Approvals page.",
            )

    async def on_workflow_failed(event: DomainEvent) -> None:
        if not isinstance(event, WorkflowFailed):
            return
        db = resolve_db()
        user_id = await _run_owner(db, UUID(event.run_id))
        if user_id:
            await dispatcher(db).dispatch(
                user_id,
                kind="workflow_failed",
                title="Workflow failed",
                body=f"A workflow run failed: {event.error}",
            )

    async def on_document_indexed(event: DomainEvent) -> None:
        if not isinstance(event, DocumentIndexed):
            return
        db = resolve_db()
        owner = await _document_owner(db, UUID(event.document_id))
        if owner:
            user_id, filename = owner
            await dispatcher(db).dispatch(
                user_id,
                kind="document_indexed",
                title="Document indexed",
                body=f"“{filename}” is indexed ({event.chunk_count} chunks) and searchable.",
            )

    bus.subscribe(ApprovalRequired, on_approval_required)
    bus.subscribe(WorkflowFailed, on_workflow_failed)
    bus.subscribe(DocumentIndexed, on_document_indexed)


async def _run_owner(db: DatabaseProvider, run_id: UUID) -> UUID | None:
    async with db.session() as session:
        run = await session.get(WorkflowRun, run_id)
        return run.user_id if run else None


async def _document_owner(
    db: DatabaseProvider, document_id: UUID
) -> tuple[UUID, str] | None:
    async with db.session() as session:
        document = await session.get(Document, document_id)
        return (document.user_id, document.filename) if document else None
