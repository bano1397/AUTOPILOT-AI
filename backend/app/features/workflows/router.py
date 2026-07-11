"""Workflow HTTP endpoints (authenticated, owner-scoped)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.pagination import PaginationParams, build_page_meta, pagination_params
from app.core.schemas import ApiResponse
from app.features.auth.dependencies import get_current_user
from app.features.users.models import User
from app.features.workflows.dependencies import get_workflow_query_service
from app.features.workflows.schemas import (
    WorkflowRunDetailRead,
    WorkflowRunRead,
    WorkflowStepRead,
)
from app.features.workflows.service import WorkflowQueryService

router = APIRouter()


@router.get("/runs", response_model=ApiResponse[list[WorkflowRunRead]])
async def list_runs(
    pagination: PaginationParams = Depends(pagination_params),
    current_user: User = Depends(get_current_user),
    service: WorkflowQueryService = Depends(get_workflow_query_service),
) -> ApiResponse[list[WorkflowRunRead]]:
    items, total = await service.list_runs(current_user.id, pagination)
    return ApiResponse(
        data=[WorkflowRunRead.model_validate(item) for item in items],
        meta=build_page_meta(pagination, total).model_dump(),
    )


@router.get("/runs/{run_id}", response_model=ApiResponse[WorkflowRunDetailRead])
async def get_run(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    service: WorkflowQueryService = Depends(get_workflow_query_service),
) -> ApiResponse[WorkflowRunDetailRead]:
    run, steps = await service.get_run(current_user.id, run_id)
    return ApiResponse(
        data=WorkflowRunDetailRead(
            run=WorkflowRunRead.model_validate(run),
            input=run.input,
            output=run.output,
            steps=[WorkflowStepRead.model_validate(step) for step in steps],
        )
    )
