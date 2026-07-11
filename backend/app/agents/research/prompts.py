"""Prompts for the research agent."""

from __future__ import annotations

from collections.abc import Sequence

from app.domain.interfaces.llm import ChatMessage, ChatRole, history_to_messages

RESEARCH_SYSTEM_PROMPT = (
    "You are AutoPilot AI's research analyst. Answer the user's question using "
    "ONLY the numbered web sources provided below. Cite the sources you used "
    "as [1], [2], etc. Be factual and concise; when sources disagree, say so. "
    "If the sources do not contain the information needed, say so plainly "
    "instead of guessing."
)


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
