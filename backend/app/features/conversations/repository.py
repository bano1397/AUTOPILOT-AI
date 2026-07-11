"""Data-access repository for conversations and messages."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.conversations.models import Conversation, Message


class ConversationRepository:
    """Persistence operations for conversations and their messages."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, conversation: Conversation) -> Conversation:
        self._session.add(conversation)
        await self._session.flush()
        return conversation

    async def get(self, conversation_id: UUID) -> Conversation | None:
        return await self._session.get(Conversation, conversation_id)

    async def list_for_user(
        self, user_id: UUID, *, offset: int, limit: int
    ) -> Sequence[Conversation]:
        result = await self._session.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()

    async def count_for_user(self, user_id: UUID) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(Conversation)
            .where(Conversation.user_id == user_id)
        )
        return int(result.scalar_one())

    async def next_position(self, conversation_id: UUID) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.max(Message.position), -1)).where(
                Message.conversation_id == conversation_id
            )
        )
        return int(result.scalar_one()) + 1

    async def add_message(
        self,
        conversation_id: UUID,
        *,
        position: int,
        role: str,
        content: str,
        meta: dict[str, Any] | None = None,
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            position=position,
            role=role,
            content=content,
            meta=meta,
        )
        self._session.add(message)
        await self._session.flush()
        return message

    async def list_messages(self, conversation_id: UUID) -> Sequence[Message]:
        result = await self._session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.position)
        )
        return result.scalars().all()

    async def recent_messages(
        self, conversation_id: UUID, *, limit: int
    ) -> list[Message]:
        result = await self._session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.position.desc())
            .limit(limit)
        )
        newest_first = list(result.scalars().all())
        return list(reversed(newest_first))
