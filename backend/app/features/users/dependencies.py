"""Dependency providers for the users feature.

This platform has **no authentication**: it is a single shared workspace (see
``docs/COMPLETION_PLAN.md`` §3). Every request runs as one implicit workspace
identity, provisioned on first use, so the owner-scoped queries in every feature
keep a stable subject to filter by. There is no login, no token, and no role —
anyone who can reach the API has full access to the instance.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session
from app.features.users.models import User
from app.features.users.repository import UserRepository
from app.features.users.service import UserService

# The single identity every request runs as. A real, non-reserved TLD: reserved
# names such as `.local` fail `EmailStr` validation on the way back out.
WORKSPACE_USER_EMAIL = "workspace@autopilot.dev"


def get_user_service(session: AsyncSession = Depends(get_db_session)) -> UserService:
    return UserService(session)


async def get_workspace_user(
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """Return the shared workspace identity, provisioning it on first use."""
    repository = UserRepository(session)
    user = await repository.get_by_email(WORKSPACE_USER_EMAIL)
    if user is not None:
        return user

    try:
        user = await repository.add(User(email=WORKSPACE_USER_EMAIL, is_active=True))
        await session.commit()
        return user
    except IntegrityError:
        # Lost a race with a concurrent first request — re-read the winner.
        await session.rollback()
        existing = await repository.get_by_email(WORKSPACE_USER_EMAIL)
        if existing is None:  # pragma: no cover - defensive
            raise
        return existing
