"""Workspace preference use-cases."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.preferences.models import WorkspacePreferences
from app.features.preferences.repository import PreferencesRepository
from app.features.preferences.schemas import PreferencesUpdateRequest


class PreferencesService:
    """Get-or-create plus partial update of the singleton preferences row."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = PreferencesRepository(session)

    async def get(self) -> WorkspacePreferences:
        existing = await self._repo.get()
        if existing is not None:
            return existing
        try:
            created = await self._repo.add(WorkspacePreferences())
            await self._session.commit()
            return created
        except IntegrityError:  # pragma: no cover - concurrent first read
            await self._session.rollback()
            racer = await self._repo.get()
            if racer is None:
                raise
            return racer

    async def update(
        self, payload: PreferencesUpdateRequest
    ) -> WorkspacePreferences:
        preferences = await self.get()
        for field, value in payload.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(preferences, field, value)
        await self._session.commit()
        await self._session.refresh(preferences)
        return preferences
