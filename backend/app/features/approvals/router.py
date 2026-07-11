"""Approval HTTP endpoints (authenticated, owner-scoped)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.pagination import PaginationParams, build_page_meta, pagination_params
from app.core.schemas import ApiResponse
from app.features.approvals.dependencies import get_approval_service
from app.features.approvals.schemas import (
    ApprovalDecisionRead,
    ApprovalDecisionRequest,
    ApprovalRead,
)
from app.features.approvals.service import ApprovalService
from app.features.auth.dependencies import get_current_user
from app.features.rag.schemas import RagMatchRead
from app.features.users.models import User

router = APIRouter()


@router.get("", response_model=ApiResponse[list[ApprovalRead]])
async def list_pending_approvals(
    pagination: PaginationParams = Depends(pagination_params),
    current_user: User = Depends(get_current_user),
    service: ApprovalService = Depends(get_approval_service),
) -> ApiResponse[list[ApprovalRead]]:
    items, total = await service.list_pending(current_user.id, pagination)
    return ApiResponse(
        data=[ApprovalRead.model_validate(item) for item in items],
        meta=build_page_meta(pagination, total).model_dump(),
    )


@router.post("/{approval_id}/decision", response_model=ApiResponse[ApprovalDecisionRead])
async def decide_approval(
    approval_id: UUID,
    payload: ApprovalDecisionRequest,
    current_user: User = Depends(get_current_user),
    service: ApprovalService = Depends(get_approval_service),
) -> ApiResponse[ApprovalDecisionRead]:
    approval, state = await service.decide(
        current_user.id, approval_id, payload.decision
    )
    return ApiResponse(
        data=ApprovalDecisionRead(
            approval=ApprovalRead.model_validate(approval),
            answer=str(state.get("answer", "")),
            agent=str(state.get("agent", "unknown")),
            grounded=bool(state.get("grounded", False)),
            model=state.get("model"),
            sources=[
                RagMatchRead.model_validate(source)
                for source in state.get("sources", [])
            ],
        )
    )
