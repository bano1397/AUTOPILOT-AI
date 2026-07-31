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
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


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


@dataclass(frozen=True)
class StreamChunk:
    """One increment of a streamed reply.

    ``delta`` is the new text only. The terminal chunk sets ``done`` and carries
    the complete :class:`LLMResult`, so usage and timing survive streaming.
    """

    delta: str = ""
    done: bool = False
    result: LLMResult | None = None


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


@runtime_checkable
class StreamingLLMProvider(Protocol):
    """Optional capability: emit the reply token-by-token as it is generated.

    Kept separate from :class:`LLMProvider` rather than added to it, because not
    every backend can stream and a provider should not have to fake it. Callers
    check ``isinstance(llm, StreamingLLMProvider)`` and fall back to a single
    ``chat()`` call, so a non-streaming provider costs responsiveness, never
    availability.

    Time-to-first-token is the number a user actually feels: a 4-second reply
    that starts rendering at 300ms reads as fast, while the same reply delivered
    whole at 4 seconds reads as broken.
    """

    # Declared without `async`: implementations are async *generators*, so
    # calling this returns the iterator directly rather than a coroutine that
    # must be awaited first.
    def chat_stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Yield chunks in order, ending with exactly one final chunk.

        The final chunk carries the assembled text and usage accounting so the
        caller never has to re-join deltas to know what was said, and the audit
        record stays as complete as the non-streaming path's.
        """
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
