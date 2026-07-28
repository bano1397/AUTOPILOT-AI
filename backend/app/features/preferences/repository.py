"""Data access for the singleton preferences row."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.preferences.models import WorkspacePreferences


class PreferencesRepository:
    """Reads and writes the one preferences record."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self) -> WorkspacePreferences | None:
        result = await self._session.execute(select(WorkspacePreferences).limit(1))
        return result.scalar_one_or_none()

    async def add(self, preferences: WorkspacePreferences) -> WorkspacePreferences:
        self._session.add(preferences)
        await self._session.flush()
        return preferences
