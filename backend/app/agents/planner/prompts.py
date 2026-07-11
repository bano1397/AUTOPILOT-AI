"""Prompts for the planner agent."""

from __future__ import annotations

from collections.abc import Sequence

from app.domain.interfaces.llm import ChatMessage, ChatRole, history_to_messages

PLANNER_SYSTEM_PROMPT = (
    "You are AutoPilot AI's planning specialist. Decompose the user's goal "
    "into 3 to 8 concrete, actionable tasks.\n"
    "Respond with ONLY a JSON array — no prose, no markdown fences. Each item "
    "must be an object with exactly these keys:\n"
    '- "title": short imperative task name (max 100 characters)\n'
    '- "description": one or two sentences of detail (may be empty)\n'
    '- "priority": one of "low", "medium", "high", "urgent"\n'
    'Example: [{"title": "Draft outline", "description": "Cover goals and '
    'scope.", "priority": "high"}]'
)


def build_planner_messages(
    goal: str, history: Sequence[dict[str, str]] = ()
) -> list[ChatMessage]:
    """Build the decomposition prompt for a goal."""
    return [
        ChatMessage(role=ChatRole.SYSTEM, content=PLANNER_SYSTEM_PROMPT),
        *history_to_messages(history),
        ChatMessage(role=ChatRole.USER, content=goal),
    ]
