"""Email HTTP endpoints (workspace-scoped).

``POST /{id}/send`` is the only path that reaches SMTP, and it exists solely to
be called by a human reviewing a draft.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.pagination import PaginationParams, build_page_meta, pagination_params
from app.core.schemas import ApiResponse
from app.features.emails.dependencies import get_email_service
from app.features.emails.models import EmailStatus
from app.features.emails.schemas import EmailRead, SendRequest, SyncResponse
from app.features.emails.service import EmailService
from app.features.users.dependencies import get_workspace_user
from app.features.users.models import User

router = APIRouter()


@router.get("", response_model=ApiResponse[list[EmailRead]])
async def list_emails(
    status: EmailStatus | None = Query(default=None),
    pagination: PaginationParams = Depends(pagination_params),
    workspace_user: User = Depends(get_workspace_user),
    service: EmailService = Depends(get_email_service),
) -> ApiResponse[list[EmailRead]]:
    items, total = await service.list_emails(workspace_user.id, pagination, status)
    return ApiResponse(
        data=[EmailRead.model_validate(mail) for mail in items],
        meta=build_page_meta(pagination, total).model_dump(),
    )


@router.post("/sync", response_model=ApiResponse[SyncResponse])
async def sync_mailbox(
    limit: int = Query(default=20, ge=1, le=50),
    workspace_user: User = Depends(get_workspace_user),
    service: EmailService = Depends(get_email_service),
) -> ApiResponse[SyncResponse]:
    summary = await service.sync(workspace_user.id, limit=limit)
    return ApiResponse(data=SyncResponse.model_validate(summary))


@router.get("/{email_id}", response_model=ApiResponse[EmailRead])
async def get_email(
    email_id: UUID,
    workspace_user: User = Depends(get_workspace_user),
    service: EmailService = Depends(get_email_service),
) -> ApiResponse[EmailRead]:
    mail = await service.get_email(workspace_user.id, email_id)
    return ApiResponse(data=EmailRead.model_validate(mail))


@router.post("/{email_id}/retriage", response_model=ApiResponse[EmailRead])
async def retriage_email(
    email_id: UUID,
    workspace_user: User = Depends(get_workspace_user),
    service: EmailService = Depends(get_email_service),
) -> ApiResponse[EmailRead]:
    mail = await service.retriage(workspace_user.id, email_id)
    return ApiResponse(data=EmailRead.model_validate(mail))


@router.post("/{email_id}/send", response_model=ApiResponse[EmailRead])
async def send_reply(
    email_id: UUID,
    payload: SendRequest,
    workspace_user: User = Depends(get_workspace_user),
    service: EmailService = Depends(get_email_service),
) -> ApiResponse[EmailRead]:
    mail = await service.send(workspace_user.id, email_id, body=payload.body)
    return ApiResponse(data=EmailRead.model_validate(mail))


@router.post("/{email_id}/discard", response_model=ApiResponse[EmailRead])
async def discard_draft(
    email_id: UUID,
    workspace_user: User = Depends(get_workspace_user),
    service: EmailService = Depends(get_email_service),
) -> ApiResponse[EmailRead]:
    mail = await service.discard(workspace_user.id, email_id)
    return ApiResponse(data=EmailRead.model_validate(mail))
