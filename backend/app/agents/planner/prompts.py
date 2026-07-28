"""Prompts for the planner agent."""

from __future__ import annotations

from collections.abc import Sequence

from app.domain.interfaces.llm import ChatMessage, ChatRole, history_to_messages
from app.platform.prompts.catalog import PLANNER_SYSTEM_PROMPT


def build_planner_messages(
    goal: str, history: Sequence[dict[str, str]] = ()
) -> list[ChatMessage]:
    """Build the decomposition prompt for a goal."""
    return [
        ChatMessage(role=ChatRole.SYSTEM, content=PLANNER_SYSTEM_PROMPT),
        *history_to_messages(history),
        ChatMessage(role=ChatRole.USER, content=goal),
    ]
