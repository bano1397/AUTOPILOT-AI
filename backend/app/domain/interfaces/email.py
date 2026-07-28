"""Email provider interface (port).

Splits mailbox reading from sending so a deployment can do one without the other
(read-only triage is useful on its own, and the send path is the dangerous one).
The default implementation is IMAP + SMTP over the standard library; a Gmail or
Graph API adapter substitutes without touching callers (blueprint §5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class InboundEmail:
    """One fetched message, already decoded to text."""

    # Server-side identifier used to mark the message seen. Stable per mailbox.
    uid: str
    message_id: str
    sender: str
    subject: str
    body: str
    received_at: datetime | None = None
    to: tuple[str, ...] = field(default_factory=tuple)


class EmailReader(Protocol):
    """Contract for reading a mailbox."""

    name: str

    async def fetch_unread(self, *, limit: int = 20) -> list[InboundEmail]:
        """Return up to ``limit`` unseen messages, oldest first."""
        ...

    async def mark_seen(self, uid: str) -> None:
        """Flag a message as seen so the next sync skips it."""
        ...


class EmailSender(Protocol):
    """Contract for sending a reply."""

    name: str

    async def send(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        in_reply_to: str | None = None,
    ) -> None:
        """Send a plain-text message."""
        ...
