"""Prompts for the research agent."""

from __future__ import annotations

from collections.abc import Sequence

from app.domain.interfaces.llm import ChatMessage, ChatRole, history_to_messages
from app.platform.prompts.catalog import RESEARCH_SYSTEM_PROMPT


def build_research_messages(
    question: str,
    sources: Sequence[dict[str, str]],
    history: Sequence[dict[str, str]] = (),
) -> list[ChatMessage]:
    """Build the synthesis prompt over the fetched web sources."""
    blocks = [
        f"[{index}] {source['title']} — {source['url']}\n{source['content']}"
        for index, source in enumerate(sources, start=1)
    ]
    user_content = (
        f"Web sources:\n\n{chr(10).join(blocks)}\n\nQuestion: {question}"
    )
    return [
        ChatMessage(role=ChatRole.SYSTEM, content=RESEARCH_SYSTEM_PROMPT),
        *history_to_messages(history),
        ChatMessage(role=ChatRole.USER, content=user_content),
    ]
