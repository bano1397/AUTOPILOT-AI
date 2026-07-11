"""Conversation use-cases: thread lifecycle, history, and exchange recording."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.pagination import PaginationParams
from app.features.conversations.models import Conversation, Message
from app.features.conversations.repository import ConversationRepository

_TITLE_MAX = 80
HISTORY_LIMIT = 10


class ConversationService:
    """Owns conversation threads and their message history."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ConversationRepository(session)

    async def resolve(
        self, user_id: UUID, conversation_id: UUID | None, first_message: str
    ) -> Conversation:
        """Return the caller's conversation, creating one when no id is given."""
        if conversation_id is None:
            title = first_message.strip()[:_TITLE_MAX] or "New conversation"
            conversation = await self._repo.add(
                Conversation(user_id=user_id, title=title)
            )
            await self._session.commit()
            return conversation

        conversation = await self._get_owned(user_id, conversation_id)
        return conversation

    async def history(self, conversation_id: UUID) -> list[dict[str, str]]:
        """Return the recent turns as role/content dicts for prompt building."""
        messages = await self._repo.recent_messages(
            conversation_id, limit=HISTORY_LIMIT
        )
        return [
            {"role": message.role, "content": message.content} for message in messages
        ]

    async def record_exchange(
        self,
        conversation_id: UUID,
        *,
        user_content: str,
        assistant_content: str,
        assistant_meta: dict[str, Any],
    ) -> None:
        """Append the user message and the assistant's reply, in order."""
        position = await self._repo.next_position(conversation_id)
        await self._repo.add_message(
            conversation_id, position=position, role="user", content=user_content
        )
        await self._repo.add_message(
            conversation_id,
            position=position + 1,
            role="assistant",
            content=assistant_content,
            meta=assistant_meta,
        )
        await self._session.commit()

    async def list_conversations(
        self, user_id: UUID, pagination: PaginationParams
    ) -> tuple[Sequence[Conversation], int]:
        items = await self._repo.list_for_user(
            user_id, offset=pagination.offset, limit=pagination.limit
        )
        total = await self._repo.count_for_user(user_id)
        return items, total

    async def get_with_messages(
        self, user_id: UUID, conversation_id: UUID
    ) -> tuple[Conversation, Sequence[Message]]:
        conversation = await self._get_owned(user_id, conversation_id)
        messages = await self._repo.list_messages(conversation_id)
        return conversation, messages

    async def _get_owned(self, user_id: UUID, conversation_id: UUID) -> Conversation:
        conversation = await self._repo.get(conversation_id)
        if conversation is None or conversation.user_id != user_id:
            # Not-found for foreign conversations too: don't leak existence.
            raise NotFoundError("Conversation not found")
        return conversation
