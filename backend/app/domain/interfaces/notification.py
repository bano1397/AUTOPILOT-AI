"""Notification provider interface (port).

Implementations deliver a notification over one channel (in-app, Telegram,
email...). The dispatcher resolves the recipient's email once and hands it to
every provider, so providers need no user lookups of their own.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class NotificationProvider(Protocol):
    """Contract for a single notification channel."""

    name: str

    async def send(
        self, *, user_id: UUID, email: str, kind: str, title: str, body: str
    ) -> None:
        """Deliver one notification to the given user."""
        ...
