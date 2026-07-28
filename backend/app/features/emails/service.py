"""Email use-cases: sync, triage, and the human-gated send.

**The approval model here is deliberate.** The LangGraph `approval_gate` pauses a
*graph run* and resumes it from a checkpoint; an email is a long-lived record
that may sit for days and be edited before sending, which is a different
lifecycle. So the gate is explicit state on the row —
``AWAITING_APPROVAL`` → a human calls ``send`` or ``discard`` — rather than a
suspended run. Nothing reaches SMTP without that human call.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.email.agent import EmailAgent
from app.core.exceptions import ConflictError, NotFoundError, UpstreamServiceError
from app.core.logging import get_logger
from app.core.pagination import PaginationParams
from app.domain.interfaces.email import EmailReader, EmailSender
from app.features.emails.models import Email, EmailStatus
from app.features.emails.repository import EmailRepository

logger = get_logger("app.features.emails")

# Statuses a human decision may act on.
_DECIDABLE = {EmailStatus.AWAITING_APPROVAL, EmailStatus.FAILED}


class EmailService:
    """Ingests, triages, and sends replies to email."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        agent: EmailAgent | None = None,
        reader: EmailReader | None = None,
        sender: EmailSender | None = None,
    ) -> None:
        self._session = session
        self._repo = EmailRepository(session)
        self._agent = agent
        self._reader = reader
        self._sender = sender

    # -- reads -----------------------------------------------------------

    async def list_emails(
        self,
        user_id: UUID,
        pagination: PaginationParams,
        status: EmailStatus | None = None,
    ) -> tuple[list[Email], int]:
        items, total = await self._repo.list_paginated(
            user_id, offset=pagination.offset, limit=pagination.limit, status=status
        )
        return list(items), total

    async def get_email(self, user_id: UUID, email_id: UUID) -> Email:
        mail = await self._repo.get(user_id, email_id)
        if mail is None:
            raise NotFoundError("Email not found")
        return mail

    # -- sync + triage ---------------------------------------------------

    async def sync(self, user_id: UUID, *, limit: int = 20) -> dict[str, int]:
        """Fetch unseen mail, persist it, and triage each message.

        Per-message failure isolation: one unparseable or LLM-failing message is
        recorded as ``failed`` and the sync continues.
        """
        if self._reader is None:
            raise UpstreamServiceError(
                "No mailbox is configured (set IMAP_HOST, IMAP_USERNAME, IMAP_PASSWORD)"
            )

        fetched = await self._reader.fetch_unread(limit=limit)
        summary = {"fetched": len(fetched), "triaged": 0, "skipped": 0, "failed": 0}

        for message in fetched:
            if await self._repo.message_id_exists(message.message_id):
                summary["skipped"] += 1
                continue

            mail = await self._repo.add(
                Email(
                    user_id=user_id,
                    uid=message.uid,
                    message_id=message.message_id,
                    sender=message.sender,
                    subject=message.subject,
                    body=message.body,
                    received_at=message.received_at,
                    status=EmailStatus.PROCESSING,
                )
            )
            await self._session.commit()

            try:
                await self._triage(mail)
                summary["triaged"] += 1
            except Exception as exc:  # noqa: BLE001 - isolate one bad message
                logger.warning(
                    "email.triage_failed",
                    extra={"email_id": str(mail.id), "error": str(exc)},
                )
                await self._session.rollback()
                await self._session.refresh(mail)
                mail.status = EmailStatus.FAILED
                mail.error = str(exc)[:2000]
                await self._session.commit()
                summary["failed"] += 1

            # Flagging is best-effort: losing the flag re-triages next sync,
            # which the message_id guard makes harmless.
            try:
                await self._reader.mark_seen(message.uid)
            except Exception:  # noqa: BLE001
                logger.warning("email.mark_seen_failed", extra={"uid": message.uid})

        return summary

    async def retriage(self, user_id: UUID, email_id: UUID) -> Email:
        """Re-run triage on one message (after a fixed provider, say)."""
        mail = await self.get_email(user_id, email_id)
        if mail.status is EmailStatus.SENT:
            raise ConflictError("This email has already been replied to")
        await self._triage(mail)
        return mail

    async def _triage(self, mail: Email) -> None:
        if self._agent is None:
            raise UpstreamServiceError("No LLM is configured for email triage")

        outcome = await self._agent.triage(
            mail.user_id, sender=mail.sender, subject=mail.subject, body=mail.body
        )
        mail.intent = outcome.classification.intent
        mail.entities = {
            **outcome.classification.entities,
            **(
                {"summary": [outcome.classification.summary]}
                if outcome.classification.summary
                else {}
            ),
        }
        mail.draft = outcome.draft
        mail.grounded = outcome.grounded
        mail.error = None
        # Spam is triaged but gets no draft, so there is nothing to approve.
        mail.status = (
            EmailStatus.AWAITING_APPROVAL if outcome.draft else EmailStatus.DISCARDED
        )
        await self._session.commit()

    # -- human decisions -------------------------------------------------

    async def send(
        self, user_id: UUID, email_id: UUID, *, body: str | None = None
    ) -> Email:
        """Send the (optionally edited) draft. The only path to SMTP."""
        mail = await self.get_email(user_id, email_id)
        if mail.status not in _DECIDABLE:
            raise ConflictError(f"Email is {mail.status.value}, not awaiting a decision")
        reply = (body or mail.draft or "").strip()
        if not reply:
            raise ConflictError("There is no draft to send")
        if self._sender is None:
            raise UpstreamServiceError(
                "No outbound mail is configured (set SMTP_HOST and SMTP_FROM)"
            )

        subject = mail.subject if mail.subject.lower().startswith("re:") else f"Re: {mail.subject}"
        # Send first, then record: a failed send must leave the row decidable
        # rather than claiming a reply that never left.
        await self._sender.send(
            to=mail.sender, subject=subject, body=reply, in_reply_to=mail.message_id
        )

        mail.draft = reply
        mail.status = EmailStatus.SENT
        mail.sent_at = datetime.now(UTC)
        await self._session.commit()
        return mail

    async def discard(self, user_id: UUID, email_id: UUID) -> Email:
        """Reject the draft; nothing is sent."""
        mail = await self.get_email(user_id, email_id)
        if mail.status is EmailStatus.SENT:
            raise ConflictError("This email has already been replied to")
        mail.status = EmailStatus.DISCARDED
        await self._session.commit()
        return mail
