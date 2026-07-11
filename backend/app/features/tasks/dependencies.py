"""Dependency providers for the tasks feature."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session
from app.features.tasks.service import TaskService


def get_task_service(session: AsyncSession = Depends(get_db_session)) -> TaskService:
    return TaskService(session)
