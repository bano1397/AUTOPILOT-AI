"""Dependency providers for the preferences feature."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session
from app.features.preferences.service import PreferencesService


def get_preferences_service(
    session: AsyncSession = Depends(get_db_session),
) -> PreferencesService:
    return PreferencesService(session)
