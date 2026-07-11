"""Prompts for the general agent."""

from __future__ import annotations

from collections.abc import Sequence

from app.domain.interfaces.llm import ChatMessage, ChatRole, history_to_messages

GENERAL_SYSTEM_PROMPT = (
    "You are AutoPilot AI, a helpful business assistant. Answer the user's "
    "message concisely and professionally. You do not have access to the "
    "user's documents in this conversation; if the request seems to need "
    "them, suggest asking a document-related question instead."
)


def build_general_messages(
    request: str, history: Sequence[dict[str, str]] = ()
) -> list[ChatMessage]:
    """Build the direct-answer prompt, preceded by prior conversation turns."""
    return [
        ChatMessage(role=ChatRole.SYSTEM, content=GENERAL_SYSTEM_PROMPT),
        *history_to_messages(history),
        ChatMessage(role=ChatRole.USER, content=request),
    ]
