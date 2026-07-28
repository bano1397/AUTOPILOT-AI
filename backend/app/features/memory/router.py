"""Long-term memory HTTP endpoints (workspace-scoped)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi import status as http_status

from app.core.pagination import PaginationParams, build_page_meta, pagination_params
from app.core.schemas import ApiResponse, MessageResponse
from app.features.memory.dependencies import get_memory_service
from app.features.memory.models import MemoryKind
from app.features.memory.schemas import (
    MemoryCreateRequest,
    MemoryRead,
    MemoryRecallRequest,
    RecollectionRead,
)
from app.features.memory.service import LongTermMemoryService
from app.features.preferences.dependencies import get_preferences_service
from app.features.preferences.service import PreferencesService
from app.features.users.dependencies import get_workspace_user
from app.features.users.models import User

router = APIRouter()


@router.get("", response_model=ApiResponse[list[MemoryRead]])
async def list_memories(
    kind: MemoryKind | None = None,
    pagination: PaginationParams = Depends(pagination_params),
    workspace_user: User = Depends(get_workspace_user),
    service: LongTermMemoryService = Depends(get_memory_service),
) -> ApiResponse[list[MemoryRead]]:
    items, total = await service.list_entries(
        workspace_user.id, pagination, kind=kind
    )
    return ApiResponse(
        data=[MemoryRead.model_validate(item) for item in items],
        meta=build_page_meta(pagination, total).model_dump(),
    )


@router.post(
    "", response_model=ApiResponse[MemoryRead], status_code=http_status.HTTP_201_CREATED
)
async def remember(
    payload: MemoryCreateRequest,
    workspace_user: User = Depends(get_workspace_user),
    service: LongTermMemoryService = Depends(get_memory_service),
) -> ApiResponse[MemoryRead]:
    entry = await service.remember(
        workspace_user.id,
        payload.content,
        kind=payload.kind,
        source=payload.source,
        meta=payload.meta,
    )
    return ApiResponse(data=MemoryRead.model_validate(entry))


@router.post("/recall", response_model=ApiResponse[list[RecollectionRead]])
async def recall(
    payload: MemoryRecallRequest,
    workspace_user: User = Depends(get_workspace_user),
    service: LongTermMemoryService = Depends(get_memory_service),
    preferences: PreferencesService = Depends(get_preferences_service),
) -> ApiResponse[list[RecollectionRead]]:
    top_k = payload.top_k or (await preferences.get()).default_top_k
    recollections = await service.recall(
        workspace_user.id, payload.query, top_k=top_k
    )
    return ApiResponse(
        data=[RecollectionRead.from_recollection(item) for item in recollections]
    )


@router.delete("/{entry_id}", response_model=ApiResponse[MessageResponse])
async def forget(
    entry_id: UUID,
    workspace_user: User = Depends(get_workspace_user),
    service: LongTermMemoryService = Depends(get_memory_service),
) -> ApiResponse[MessageResponse]:
    await service.forget(workspace_user.id, entry_id)
    return ApiResponse(data=MessageResponse(message="Memory forgotten"))
