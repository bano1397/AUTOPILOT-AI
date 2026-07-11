"""Task HTTP endpoints (authenticated, owner-scoped)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi import status as http_status

from app.core.pagination import PaginationParams, build_page_meta, pagination_params
from app.core.schemas import ApiResponse, MessageResponse
from app.features.auth.dependencies import get_current_user
from app.features.tasks.dependencies import get_task_service
from app.features.tasks.models import TaskStatus
from app.features.tasks.schemas import TaskCreateRequest, TaskRead, TaskUpdateRequest
from app.features.tasks.service import TaskService
from app.features.users.models import User

router = APIRouter()


@router.get("", response_model=ApiResponse[list[TaskRead]])
async def list_tasks(
    status: TaskStatus | None = None,
    pagination: PaginationParams = Depends(pagination_params),
    current_user: User = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> ApiResponse[list[TaskRead]]:
    items, total = await service.list_tasks(current_user.id, pagination, status)
    return ApiResponse(
        data=[TaskRead.model_validate(item) for item in items],
        meta=build_page_meta(pagination, total).model_dump(),
    )


@router.post(
    "", response_model=ApiResponse[TaskRead], status_code=http_status.HTTP_201_CREATED
)
async def create_task(
    payload: TaskCreateRequest,
    current_user: User = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> ApiResponse[TaskRead]:
    task = await service.create(current_user.id, payload)
    return ApiResponse(data=TaskRead.model_validate(task))


@router.patch("/{task_id}", response_model=ApiResponse[TaskRead])
async def update_task(
    task_id: UUID,
    payload: TaskUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> ApiResponse[TaskRead]:
    task = await service.update(current_user.id, task_id, payload)
    return ApiResponse(data=TaskRead.model_validate(task))


@router.delete("/{task_id}", response_model=ApiResponse[MessageResponse])
async def delete_task(
    task_id: UUID,
    current_user: User = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> ApiResponse[MessageResponse]:
    await service.delete(current_user.id, task_id)
    return ApiResponse(data=MessageResponse(message="Task deleted"))
