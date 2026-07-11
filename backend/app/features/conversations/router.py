"""Conversation HTTP endpoints (authenticated, owner-scoped)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.pagination import PaginationParams, build_page_meta, pagination_params
from app.core.schemas import ApiResponse
from app.features.auth.dependencies import get_current_user
from app.features.conversations.dependencies import get_conversation_service
from app.features.conversations.schemas import (
    ConversationDetailRead,
    ConversationRead,
    MessageRead,
)
from app.features.conversations.service import ConversationService
from app.features.users.models import User

router = APIRouter()


@router.get("", response_model=ApiResponse[list[ConversationRead]])
async def list_conversations(
    pagination: PaginationParams = Depends(pagination_params),
    current_user: User = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
) -> ApiResponse[list[ConversationRead]]:
    items, total = await service.list_conversations(current_user.id, pagination)
    return ApiResponse(
        data=[ConversationRead.model_validate(item) for item in items],
        meta=build_page_meta(pagination, total).model_dump(),
    )


@router.get("/{conversation_id}", response_model=ApiResponse[ConversationDetailRead])
async def get_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
) -> ApiResponse[ConversationDetailRead]:
    conversation, messages = await service.get_with_messages(
        current_user.id, conversation_id
    )
    return ApiResponse(
        data=ConversationDetailRead(
            conversation=ConversationRead.model_validate(conversation),
            messages=[MessageRead.model_validate(message) for message in messages],
        )
    )
