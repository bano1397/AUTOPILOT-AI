"""Dependency providers for the calendar feature."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dependencies import get_db_session
from app.domain.interfaces.calendar import CalendarProvider
from app.features.users.dependencies import get_workspace_user
from app.features.users.models import User
from app.infrastructure.calendar import GoogleCalendarProvider, LocalCalendarProvider


def get_calendar_provider(
    session: AsyncSession = Depends(get_db_session),
    workspace_user: User = Depends(get_workspace_user),
) -> CalendarProvider:
    """Select the calendar backend from config.

    Request-scoped rather than application-scoped, unlike the other providers:
    the local adapter needs the request's database session, and calendars are
    owner-scoped in a way an LLM client is not.
    """
    if get_settings().calendar_provider == "google":
        return GoogleCalendarProvider()
    return LocalCalendarProvider(session, workspace_user.id)
