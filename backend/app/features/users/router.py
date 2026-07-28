"""Workspace identity and user listing endpoints.

There is no authentication and no role model (see ``docs/COMPLETION_PLAN.md``
§3), so these endpoints are open. ``GET /me`` returns the shared workspace
identity the whole instance runs as; the listing exists for introspection.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.pagination import PaginationParams, build_page_meta, pagination_params
from app.core.schemas import ApiResponse
from app.features.users.dependencies import get_user_service, get_workspace_user
from app.features.users.models import User
from app.features.users.schemas import UserRead
from app.features.users.service import UserService

router = APIRouter()


# Declared before `/{user_id}` so the literal path wins over the UUID converter.
@router.get("/me", response_model=ApiResponse[UserRead])
async def get_me(
    workspace_user: User = Depends(get_workspace_user),
) -> ApiResponse[UserRead]:
    return ApiResponse(data=UserRead.model_validate(workspace_user))


@router.get("", response_model=ApiResponse[list[UserRead]])
async def list_users(
    pagination: PaginationParams = Depends(pagination_params),
    service: UserService = Depends(get_user_service),
) -> ApiResponse[list[UserRead]]:
    items, total = await service.list_users(pagination)
    meta = build_page_meta(pagination, total)
    return ApiResponse(
        data=[UserRead.model_validate(user) for user in items],
        meta=meta.model_dump(),
    )


@router.get("/{user_id}", response_model=ApiResponse[UserRead])
async def get_user(
    user_id: UUID,
    service: UserService = Depends(get_user_service),
) -> ApiResponse[UserRead]:
    user = await service.get_user(user_id)
    return ApiResponse(data=UserRead.model_validate(user))
