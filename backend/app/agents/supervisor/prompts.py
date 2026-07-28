"""Prompts for the supervisor's routing decision."""

from __future__ import annotations

from app.domain.interfaces.llm import ChatMessage, ChatRole
from app.platform.prompts.catalog import ROUTING_SYSTEM_PROMPT


def build_routing_messages(request: str) -> list[ChatMessage]:
    """Build the classification prompt for a user request."""
    return [
        ChatMessage(role=ChatRole.SYSTEM, content=ROUTING_SYSTEM_PROMPT),
        ChatMessage(role=ChatRole.USER, content=request),
    ]
