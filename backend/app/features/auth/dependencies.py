"""Dependency providers for the auth feature.

Authentication has been intentionally disabled for the public demo deployment:
``get_current_user`` no longer requires a bearer token. Instead it resolves a
single shared "public workspace" user (created on first use), so every
owner-scoped feature keeps working while the app is open to anyone. The login/
register endpoints remain available but are not required to use the app.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session
from app.core.exceptions import PermissionDeniedError
from app.features.auth.service import AuthService
from app.features.users.models import User, UserRole
from app.features.users.repository import UserRepository

# The shared account every request runs as while auth is disabled.
PUBLIC_USER_EMAIL = "public@autopilot.local"


def get_auth_service(session: AsyncSession = Depends(get_db_session)) -> AuthService:
    return AuthService(session)


async def get_current_user(
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """Return the shared public workspace user (auth disabled; get-or-create)."""
    repository = UserRepository(session)
    user = await repository.get_by_email(PUBLIC_USER_EMAIL)
    if user is not None:
        return user

    # First ever request: provision the shared account. Admin role so the open
    # app can reach admin-guarded endpoints too. The password hash is a
    # non-verifiable placeholder — login is not used in this mode.
    try:
        user = await repository.add(
            User(
                email=PUBLIC_USER_EMAIL,
                password_hash="!disabled",  # noqa: S106 - auth disabled, never verified
                role=UserRole.ADMIN,
                is_active=True,
            )
        )
        await session.commit()
        return user
    except IntegrityError:
        # Lost a race with a concurrent first request — re-read the winner.
        await session.rollback()
        existing = await repository.get_by_email(PUBLIC_USER_EMAIL)
        if existing is None:  # pragma: no cover - defensive
            raise
        return existing


def require_role(*roles: UserRole) -> Callable[..., Awaitable[User]]:
    """Build a dependency that authorizes only the given roles."""

    async def _require(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise PermissionDeniedError("Insufficient permissions for this resource")
        return current_user

    return _require


# Convenience guard for admin-only endpoints.
require_admin = require_role(UserRole.ADMIN)
