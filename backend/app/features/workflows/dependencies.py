"""Dependency providers for the workflows feature."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_database, get_db_session, get_event_bus
from app.domain.interfaces.database import DatabaseProvider
from app.domain.interfaces.event_bus import EventBus
from app.features.workflows.lifecycle import WorkflowLifecycleService
from app.features.workflows.service import WorkflowExecutor, WorkflowQueryService


def get_workflow_executor(
    db: DatabaseProvider = Depends(get_database),
    bus: EventBus = Depends(get_event_bus),
) -> WorkflowExecutor:
    return WorkflowExecutor(db, bus)


def get_workflow_query_service(
    session: AsyncSession = Depends(get_db_session),
) -> WorkflowQueryService:
    return WorkflowQueryService(session)


def get_workflow_lifecycle_service(
    session: AsyncSession = Depends(get_db_session),
) -> WorkflowLifecycleService:
    return WorkflowLifecycleService(session)
