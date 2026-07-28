"""Prompts for the general agent."""

from __future__ import annotations

from collections.abc import Sequence

from app.domain.interfaces.llm import ChatMessage, ChatRole, history_to_messages
from app.platform.prompts.catalog import GENERAL_SYSTEM_PROMPT


def build_general_messages(
    request: str, history: Sequence[dict[str, str]] = ()
) -> list[ChatMessage]:
    """Build the direct-answer prompt, preceded by prior conversation turns."""
    return [
        ChatMessage(role=ChatRole.SYSTEM, content=GENERAL_SYSTEM_PROMPT),
        *history_to_messages(history),
        ChatMessage(role=ChatRole.USER, content=request),
    ]
