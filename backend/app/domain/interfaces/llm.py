"""LLM interface (port).

Chat-completion contract for all text generation. The default implementation
calls a local Ollama instance; hosted providers (Anthropic, OpenAI, ...) can be
substituted without changing callers (blueprint §5, provider #1).

:class:`LLMResult` deliberately carries token counts and timing — the AI
observability record (blueprint §10) and the cost dashboard (§22) consume them
for every call, so the contract exposes them from the start.
"""

from __future__ import annotations

import enum
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


class ChatRole(str, enum.Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class ChatMessage:
    """One turn of a chat conversation."""

    role: ChatRole
    content: str


@dataclass(frozen=True)
class LLMResult:
    """A completed generation with its usage accounting."""

    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    duration_ms: int = 0


class LLMProvider(Protocol):
    """Contract for chat-completion backends."""

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResult:
        """Generate the assistant's next message for the given conversation."""
        ...


def history_to_messages(history: Sequence[dict[str, str]]) -> list[ChatMessage]:
    """Convert stored role/content turns into chat messages.

    Unknown roles are skipped rather than raising: history is data, and a bad
    row must not break prompt building.
    """
    valid = {role.value for role in ChatRole}
    return [
        ChatMessage(role=ChatRole(turn["role"]), content=turn.get("content", ""))
        for turn in history
        if turn.get("role") in valid
    ]
