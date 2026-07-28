"""Dependency providers for the emails feature.

The mailbox providers are optional: with no IMAP/SMTP configuration the API still
serves reads and returns a clear 502 on sync or send, rather than the app failing
to boot.
"""

from __future__ import annotations

from typing import cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.email.agent import EmailAgent
from app.core.dependencies import get_db_session
from app.domain.interfaces.email import EmailReader, EmailSender
from app.features.emails.service import EmailService
from app.features.rag.service import RagService


def get_email_service(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> EmailService:
    state = request.app.state
    agent = EmailAgent(
        llm=state.llm,
        recorder=state.ai_recorder,
        rag=RagService(state.embeddings, state.vector_store),
    )
    return EmailService(
        session,
        agent=agent,
        reader=cast("EmailReader | None", getattr(state, "email_reader", None)),
        sender=cast("EmailSender | None", getattr(state, "email_sender", None)),
    )
