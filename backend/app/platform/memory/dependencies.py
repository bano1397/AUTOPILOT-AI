"""Dependency provider assembling the :class:`MemoryManager` facade.

Lives beside the facade rather than in a feature module because it composes
several features; putting it in any one of them would invert the dependency.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_checkpointer, get_db_session
from app.features.conversations.service import ConversationService
from app.features.memory.dependencies import get_memory_service
from app.features.memory.service import LongTermMemoryService
from app.features.preferences.dependencies import get_preferences_service
from app.features.preferences.service import PreferencesService
from app.features.rag.dependencies import get_rag_service
from app.features.rag.service import RagService
from app.platform.memory.manager import MemoryManager


def get_memory_manager(
    session: AsyncSession = Depends(get_db_session),
    long_term: LongTermMemoryService = Depends(get_memory_service),
    knowledge: RagService = Depends(get_rag_service),
    preferences: PreferencesService = Depends(get_preferences_service),
    checkpointer: object | None = Depends(get_checkpointer),
) -> MemoryManager:
    return MemoryManager(
        long_term=long_term,
        conversations=ConversationService(session),
        knowledge=knowledge,
        preferences=preferences,
        checkpointer=checkpointer,
    )
