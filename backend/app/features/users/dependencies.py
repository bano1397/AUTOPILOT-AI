"""Dependency providers for the users feature."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session
from app.features.users.service import UserService


def get_user_service(session: AsyncSession = Depends(get_db_session)) -> UserService:
    return UserService(session)
