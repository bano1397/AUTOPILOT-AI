"""Prompts for RAG-grounded answering.

Kept separate from business logic per the project rules: prompt text is an
artifact to review and iterate on independently of the code that uses it.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.domain.interfaces.llm import ChatMessage, ChatRole, history_to_messages
from app.domain.interfaces.vector_store import VectorMatch

SYSTEM_PROMPT = (
    "You are AutoPilot AI's knowledge assistant. Answer the user's question "
    "using ONLY the numbered context excerpts provided below. Cite the "
    "excerpts you used as [1], [2], etc. If the context does not contain the "
    "information needed to answer, say so plainly instead of guessing. Be "
    "concise and factual."
)


def _format_context(matches: Sequence[VectorMatch]) -> str:
    blocks: list[str] = []
    for position, match in enumerate(matches, start=1):
        filename = str(match.metadata.get("filename", "document"))
        chunk_index = int(match.metadata.get("chunk_index", 0))
        blocks.append(f"[{position}] {filename} (part {chunk_index + 1}):\n{match.text}")
    return "\n\n".join(blocks)


def build_ask_messages(
    question: str,
    matches: Sequence[VectorMatch],
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
