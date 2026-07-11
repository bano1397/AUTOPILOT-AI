"""SMTP (email) notification provider.

Uses the standard library ``smtplib`` offloaded to a worker thread — no extra
dependency, same pattern as the file-storage and extraction providers.
"""

from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage
from uuid import UUID

from app.platform.registry import register_provider


@register_provider(kind="notification", name="smtp")
class SmtpNotificationProvider:
    """Sends notification emails to the user's account address."""

    name = "smtp"

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str | None,
        password: str | None,
        sender: str,
        use_tls: bool = True,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._sender = sender
        self._use_tls = use_tls

    async def send(
        self, *, user_id: UUID, email: str, kind: str, title: str, body: str
    ) -> None:
        await asyncio.to_thread(self._send_sync, email, title, body)

    def _send_sync(self, recipient: str, title: str, body: str) -> None:
        message = EmailMessage()
        message["Subject"] = f"[AutoPilot AI] {title}"
        message["From"] = self._sender
        message["To"] = recipient
        message.set_content(body)

        with smtplib.SMTP(self._host, self._port, timeout=15) as smtp:
            if self._use_tls:
                smtp.starttls()
            if self._username and self._password:
                smtp.login(self._username, self._password)
            smtp.send_message(message)
