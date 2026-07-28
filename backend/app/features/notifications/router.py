"""Notification HTTP endpoints (workspace-scoped)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session
from app.core.pagination import PaginationParams, build_page_meta, pagination_params
from app.core.schemas import ApiResponse
from app.features.notifications.schemas import (
    MarkAllReadRead,
    NotificationRead,
    UnreadCountRead,
)
from app.features.notifications.service import NotificationService
from app.features.users.dependencies import get_workspace_user
from app.features.users.models import User

router = APIRouter()


def get_notification_service(
    session: AsyncSession = Depends(get_db_session),
) -> NotificationService:
    return NotificationService(session)


@router.get("", response_model=ApiResponse[list[NotificationRead]])
async def list_notifications(
    pagination: PaginationParams = Depends(pagination_params),
    workspace_user: User = Depends(get_workspace_user),
    service: NotificationService = Depends(get_notification_service),
) -> ApiResponse[list[NotificationRead]]:
    items, total = await service.list_notifications(workspace_user.id, pagination)
    return ApiResponse(
        data=[NotificationRead.model_validate(item) for item in items],
        meta=build_page_meta(pagination, total).model_dump(),
    )


@router.get("/unread-count", response_model=ApiResponse[UnreadCountRead])
async def unread_count(
    workspace_user: User = Depends(get_workspace_user),
    service: NotificationService = Depends(get_notification_service),
) -> ApiResponse[UnreadCountRead]:
    count = await service.unread_count(workspace_user.id)
    return ApiResponse(data=UnreadCountRead(count=count))


@router.post("/{notification_id}/read", response_model=ApiResponse[NotificationRead])
async def mark_read(
    notification_id: UUID,
    workspace_user: User = Depends(get_workspace_user),
    service: NotificationService = Depends(get_notification_service),
) -> ApiResponse[NotificationRead]:
    notification = await service.mark_read(workspace_user.id, notification_id)
    return ApiResponse(data=NotificationRead.model_validate(notification))


@router.post("/read-all", response_model=ApiResponse[MarkAllReadRead])
async def mark_all_read(
    workspace_user: User = Depends(get_workspace_user),
    service: NotificationService = Depends(get_notification_service),
) -> ApiResponse[MarkAllReadRead]:
    updated = await service.mark_all_read(workspace_user.id)
    return ApiResponse(data=MarkAllReadRead(updated=updated))
