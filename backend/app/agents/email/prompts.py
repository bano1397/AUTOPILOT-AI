"""Prompt builders for the email agent."""

from __future__ import annotations

from collections.abc import Sequence

from app.domain.interfaces.llm import ChatMessage, ChatRole
from app.platform.prompts.catalog import (
    EMAIL_CLASSIFY_SYSTEM_PROMPT,
    EMAIL_DRAFT_SYSTEM_PROMPT,
)
from app.platform.rag.types import RetrievedChunk


def build_classify_messages(sender: str, subject: str, body: str) -> list[ChatMessage]:
    """Build the intent+entity extraction prompt for one message."""
    return [
        ChatMessage(role=ChatRole.SYSTEM, content=EMAIL_CLASSIFY_SYSTEM_PROMPT),
        ChatMessage(
            role=ChatRole.USER,
            content=f"From: {sender}\nSubject: {subject}\n\n{body[:4000]}",
        ),
    ]


def build_draft_messages(
    sender: str,
    subject: str,
    body: str,
    intent: str,
    matches: Sequence[RetrievedChunk] = (),
) -> list[ChatMessage]:
    """Build the reply-drafting prompt, grounded in retrieved context if any."""
    if matches:
        context = "\n\n".join(
            f"[{position}] {match.filename or 'document'}:\n{match.text}"
            for position, match in enumerate(matches, start=1)
        )
        grounding = (
            f"Company knowledge you may cite as [1], [2], …:\n\n{context}\n\n"
        )
    else:
        grounding = (
            "No company documents matched this message. Do not invent policy, "
            "prices, or commitments — keep the reply general and offer to follow "
            "up.\n\n"
        )

    return [
        ChatMessage(role=ChatRole.SYSTEM, content=EMAIL_DRAFT_SYSTEM_PROMPT),
        ChatMessage(
            role=ChatRole.USER,
            content=(
                f"{grounding}"
                f"Classified intent: {intent}\n\n"
                f"Message to reply to —\nFrom: {sender}\nSubject: {subject}\n\n"
                f"{body[:4000]}"
            ),
        ),
    ]
