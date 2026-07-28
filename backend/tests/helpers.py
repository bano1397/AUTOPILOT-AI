"""Test helpers shared across the integration suite.

With authentication removed (``docs/COMPLETION_PLAN.md`` §3) tests no longer
register users or acquire tokens: every request runs as the shared workspace
identity. Tests that need to seed rows directly in the database ask for that
identity's id with :func:`workspace_user_id`.
"""

from __future__ import annotations

from uuid import UUID

from app.features.users.dependencies import WORKSPACE_USER_EMAIL
from app.features.users.models import User
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from sqlalchemy import select


async def workspace_user_id(db: SqlAlchemyDatabaseProvider) -> UUID:
    """Return the workspace identity's id, provisioning the row if absent.

    Mirrors what the request dependency does, so seeded rows land on the same
    owner the API will resolve.
    """
    async with db.session() as session:
        result = await session.execute(
            select(User).where(User.email == WORKSPACE_USER_EMAIL)
        )
        user = result.scalar_one_or_none()
        if user is None:
            user = User(email=WORKSPACE_USER_EMAIL, is_active=True)
            session.add(user)
            await session.commit()
            await session.refresh(user)
        return user.id
