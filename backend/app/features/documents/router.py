"""Document HTTP endpoints (workspace-scoped)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, UploadFile, status

from app.core.config import get_settings
from app.core.pagination import PaginationParams, build_page_meta, pagination_params
from app.core.schemas import ApiResponse, MessageResponse
from app.features.documents.dependencies import get_document_service
from app.features.documents.schemas import DocumentRead
from app.features.documents.service import DocumentService
from app.features.users.dependencies import get_workspace_user
from app.features.users.models import User

router = APIRouter()


@router.post(
    "",
    response_model=ApiResponse[DocumentRead],
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile,
    workspace_user: User = Depends(get_workspace_user),
    service: DocumentService = Depends(get_document_service),
) -> ApiResponse[DocumentRead]:
    # Read at most one byte past the limit; the service rejects oversizes
    # without this process ever buffering an arbitrarily large body.
    max_bytes = get_settings().max_upload_size_mb * 1024 * 1024
    content = await file.read(max_bytes + 1)
    document = await service.upload(
        workspace_user,
        filename=file.filename,
        content=content,
        declared_mime=file.content_type,
    )
    return ApiResponse(data=DocumentRead.model_validate(document))


@router.get("", response_model=ApiResponse[list[DocumentRead]])
async def list_documents(
    pagination: PaginationParams = Depends(pagination_params),
    workspace_user: User = Depends(get_workspace_user),
    service: DocumentService = Depends(get_document_service),
) -> ApiResponse[list[DocumentRead]]:
    items, total = await service.list_documents(workspace_user, pagination)
    meta = build_page_meta(pagination, total)
    return ApiResponse(
        data=[DocumentRead.model_validate(document) for document in items],
        meta=meta.model_dump(),
    )


@router.get("/{document_id}", response_model=ApiResponse[DocumentRead])
async def get_document(
    document_id: UUID,
    workspace_user: User = Depends(get_workspace_user),
    service: DocumentService = Depends(get_document_service),
) -> ApiResponse[DocumentRead]:
    document = await service.get_document(workspace_user, document_id)
    return ApiResponse(data=DocumentRead.model_validate(document))


@router.post("/{document_id}/reindex", response_model=ApiResponse[DocumentRead])
async def reindex_document(
    document_id: UUID,
    workspace_user: User = Depends(get_workspace_user),
    service: DocumentService = Depends(get_document_service),
) -> ApiResponse[DocumentRead]:
    """Re-run ingestion over the stored file, keeping the document id.

    Use after changing chunk size, enabling OCR, or to give a document indexed
    before hybrid search the persisted chunk text keyword search needs.
    """
    document = await service.reindex_document(workspace_user, document_id)
    return ApiResponse(data=DocumentRead.model_validate(document))


@router.delete("/{document_id}", response_model=ApiResponse[MessageResponse])
async def delete_document(
    document_id: UUID,
    workspace_user: User = Depends(get_workspace_user),
    service: DocumentService = Depends(get_document_service),
) -> ApiResponse[MessageResponse]:
    await service.delete_document(workspace_user, document_id)
    return ApiResponse(data=MessageResponse(message="Document deleted"))
