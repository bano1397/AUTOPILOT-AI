"""Prompts for the general agent."""

from __future__ import annotations

from collections.abc import Sequence

from app.domain.interfaces.llm import ChatMessage, ChatRole, history_to_messages
from app.platform.prompts.catalog import GENERAL_SYSTEM_PROMPT_V2

GENERAL_PROMPT_KEY = "agent.general.system"
GENERAL_PROMPT_VERSION = 2


def build_general_messages(
    request: str,
    history: Sequence[dict[str, str]] = (),
    memories: Sequence[str] = (),
) -> list[ChatMessage]:
    """Build the direct-answer prompt, preceded by prior conversation turns.

    ``memories`` are recalled durable facts (level 3). With none, the rendered
    system message is byte-identical to the one v1 produced.
    """
    system = GENERAL_SYSTEM_PROMPT_V2.render(memories=list(memories))
    return [
        ChatMessage(role=ChatRole.SYSTEM, content=system),
        *history_to_messages(history),
        ChatMessage(role=ChatRole.USER, content=request),
    ]
