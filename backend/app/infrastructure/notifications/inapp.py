"""In-app notification provider: persists notifications to the database."""

from __future__ import annotations

from uuid import UUID

from app.domain.interfaces.database import DatabaseProvider
from app.features.notifications.models import Notification
from app.platform.registry import register_provider


@register_provider(kind="notification", name="in_app")
class InAppNotificationProvider:
    """Always-on channel backing the bell in the dashboard."""

    name = "in_app"

    def __init__(self, db: DatabaseProvider) -> None:
        self._db = db

    async def send(
        self, *, user_id: UUID, email: str, kind: str, title: str, body: str
    ) -> None:
        async with self._db.session() as session:
            session.add(
                Notification(user_id=user_id, type=kind, title=title, body=body)
            )
            await session.commit()
