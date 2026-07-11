"""Notification dispatcher: fan-out to every configured channel.

Provider failures are isolated per channel — a dead Telegram token must never
block the in-app row, and no channel failure may break the emitting workflow.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from app.core.logging import get_logger
from app.domain.interfaces.database import DatabaseProvider
from app.domain.interfaces.notification import NotificationProvider
from app.features.users.repository import UserRepository

logger = get_logger("app.notifications")


class NotificationDispatcher:
    """Resolves the recipient once and delivers over all channels."""

    def __init__(
        self, db: DatabaseProvider, providers: Sequence[NotificationProvider]
    ) -> None:
        self._db = db
        self._providers = providers

    async def dispatch(
        self, user_id: UUID, *, kind: str, title: str, body: str
    ) -> None:
        email = await self._resolve_email(user_id)
        if email is None:
            logger.warning("notification.user_missing", extra={"user_id": str(user_id)})
            return

        for provider in self._providers:
            try:
                await provider.send(
                    user_id=user_id, email=email, kind=kind, title=title, body=body
                )
            except Exception:  # noqa: BLE001 - channel isolation is intentional
                logger.exception(
                    "notification.channel_failed",
                    extra={"provider": provider.name, "kind": kind},
                )

    async def _resolve_email(self, user_id: UUID) -> str | None:
        async with self._db.session() as session:
            user = await UserRepository(session).get_by_id(user_id)
            return user.email if user else None
