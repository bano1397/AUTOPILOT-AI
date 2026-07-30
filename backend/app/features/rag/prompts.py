"""Prompts for RAG-grounded answering.

Kept separate from business logic per the project rules: prompt text is an
artifact to review and iterate on independently of the code that uses it.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.domain.interfaces.llm import ChatMessage, ChatRole, history_to_messages
from app.platform.prompts.catalog import SYSTEM_PROMPT
from app.platform.rag.types import RetrievedChunk


def _format_context(matches: Sequence[RetrievedChunk]) -> str:
    blocks: list[str] = []
    for position, match in enumerate(matches, start=1):
        filename = match.filename or "document"
        blocks.append(
            f"[{position}] {filename} (part {match.chunk_index + 1}):\n{match.text}"
        )
    return "\n\n".join(blocks)


def build_ask_messages(
    question: str,
    matches: Sequence[RetrievedChunk],
    history: Sequence[dict[str, str]] = (),
) -> list[ChatMessage]:
    """Build the grounded chat prompt for a question and its retrieved context.

    Prior turns (if any) precede the grounded question so follow-ups like
    "and what about part-timers?" keep their meaning.
    """
    user_content = (
        f"Context excerpts:\n\n{_format_context(matches)}\n\n"
        f"Question: {question}"
    )
    return [
        ChatMessage(role=ChatRole.SYSTEM, content=SYSTEM_PROMPT),
        *history_to_messages(history),
        ChatMessage(role=ChatRole.USER, content=user_content),
    ]
