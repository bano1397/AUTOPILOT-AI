"""IMAP reader and SMTP sender over the standard library.

Both use blocking stdlib clients (``imaplib`` / ``smtplib``) executed in worker
threads, the same pattern as the SMTP notification channel — no new dependency
for a protocol Python already speaks.

Connections are per-operation rather than pooled: a mailbox sync runs on a
schedule or on demand, so the connection cost is irrelevant next to the
robustness of never holding a stale socket.
"""

from __future__ import annotations

import asyncio
import email
import imaplib
import smtplib
from email.message import EmailMessage

from app.core.exceptions import UpstreamServiceError
from app.core.logging import get_logger
from app.domain.interfaces.email import InboundEmail
from app.infrastructure.email.parsing import (
    decode_header_value,
    extract_body,
    parse_date,
)
from app.platform.registry import register_provider

logger = get_logger("app.email")

_TIMEOUT = 30


@register_provider(kind="email_reader", name="imap")
class ImapEmailReader:
    """Reads unseen messages from an IMAP mailbox."""

    name = "imap"

    def __init__(
        self,
        *,
        host: str,
        username: str,
        password: str,
        port: int = 993,
        mailbox: str = "INBOX",
        use_ssl: bool = True,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._mailbox = mailbox
        self._use_ssl = use_ssl

    def _connect(self) -> imaplib.IMAP4:
        if self._use_ssl:
            connection: imaplib.IMAP4 = imaplib.IMAP4_SSL(
                self._host, self._port, timeout=_TIMEOUT
            )
        else:
            connection = imaplib.IMAP4(self._host, self._port, timeout=_TIMEOUT)
        connection.login(self._username, self._password)
        return connection

    def _fetch_blocking(self, limit: int) -> list[InboundEmail]:
        connection = self._connect()
        try:
            connection.select(self._mailbox)
            status, data = connection.search(None, "UNSEEN")
            if status != "OK" or not data or not data[0]:
                return []
            uids = data[0].split()[:limit]

            messages: list[InboundEmail] = []
            for raw_uid in uids:
                # BODY.PEEK leaves the message unseen: marking it read is an
                # explicit, separate decision (see mark_seen).
                status, payload = connection.fetch(raw_uid, "(BODY.PEEK[])")
                if status != "OK" or not payload:
                    continue
                body_bytes = next(
                    (part[1] for part in payload if isinstance(part, tuple)), None
                )
                if not isinstance(body_bytes, bytes):
                    continue
                parsed = email.message_from_bytes(body_bytes)
                uid = raw_uid.decode()
                messages.append(
                    InboundEmail(
                        uid=uid,
                        message_id=decode_header_value(parsed.get("Message-ID")) or uid,
                        sender=decode_header_value(parsed.get("From")),
                        subject=decode_header_value(parsed.get("Subject")),
                        body=extract_body(parsed),
                        received_at=parse_date(parsed.get("Date")),
                        to=tuple(
                            filter(None, [decode_header_value(parsed.get("To"))])
                        ),
                    )
                )
            return messages
        finally:
            try:
                connection.logout()
            except OSError:  # pragma: no cover - best-effort close
                pass

    async def fetch_unread(self, *, limit: int = 20) -> list[InboundEmail]:
        try:
            return await asyncio.to_thread(self._fetch_blocking, limit)
        except (imaplib.IMAP4.error, OSError) as exc:
            logger.warning("email.imap_fetch_failed", extra={"error": str(exc)})
            raise UpstreamServiceError(f"IMAP mailbox unavailable: {exc}") from exc

    def _mark_seen_blocking(self, uid: str) -> None:
        connection = self._connect()
        try:
            connection.select(self._mailbox)
            connection.store(uid, "+FLAGS", "\\Seen")
        finally:
            try:
                connection.logout()
            except OSError:  # pragma: no cover
                pass

    async def mark_seen(self, uid: str) -> None:
        try:
            await asyncio.to_thread(self._mark_seen_blocking, uid)
        except (imaplib.IMAP4.error, OSError) as exc:
            logger.warning("email.imap_flag_failed", extra={"error": str(exc)})
            raise UpstreamServiceError(f"IMAP mailbox unavailable: {exc}") from exc


@register_provider(kind="email_sender", name="smtp")
class SmtpEmailSender:
    """Sends plain-text replies over SMTP."""

    name = "smtp"

    def __init__(
        self,
        *,
        host: str,
        sender: str,
        port: int = 587,
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = True,
    ) -> None:
        self._host = host
        self._port = port
        self._sender = sender
        self._username = username
        self._password = password
        self._use_tls = use_tls

    def _send_blocking(self, message: EmailMessage) -> None:
        with smtplib.SMTP(self._host, self._port, timeout=_TIMEOUT) as smtp:
            if self._use_tls:
                smtp.starttls()
            if self._username and self._password:
                smtp.login(self._username, self._password)
            smtp.send_message(message)

    async def send(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        in_reply_to: str | None = None,
    ) -> None:
        message = EmailMessage()
        message["From"] = self._sender
        message["To"] = to
        message["Subject"] = subject
        if in_reply_to:
            # Threads the reply in the recipient's client.
            message["In-Reply-To"] = in_reply_to
            message["References"] = in_reply_to
        message.set_content(body)

        try:
            await asyncio.to_thread(self._send_blocking, message)
        except (smtplib.SMTPException, OSError) as exc:
            logger.warning("email.smtp_send_failed", extra={"error": str(exc)})
            raise UpstreamServiceError(f"SMTP send failed: {exc}") from exc
