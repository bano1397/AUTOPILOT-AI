"""RAG HTTP endpoints (authenticated, owner-isolated)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.schemas import ApiResponse
from app.features.auth.dependencies import get_current_user
from app.features.rag.dependencies import get_rag_ask_service, get_rag_service
from app.features.rag.schemas import (
    RagAskRead,
    RagAskRequest,
    RagMatchRead,
    RagQueryRead,
    RagQueryRequest,
)
from app.features.rag.service import RagAskService, RagService
from app.features.users.models import User

router = APIRouter()


@router.post("/query", response_model=ApiResponse[RagQueryRead])
async def query_documents(
    payload: RagQueryRequest,
    current_user: User = Depends(get_current_user),
    service: RagService = Depends(get_rag_service),
) -> ApiResponse[RagQueryRead]:
    matches = await service.query(current_user.id, payload.query, top_k=payload.top_k)
    return ApiResponse(
        data=RagQueryRead(
            query=payload.query,
            matches=[RagMatchRead.from_vector_match(match) for match in matches],
        )
    )


@router.post("/ask", response_model=ApiResponse[RagAskRead])
async def ask_documents(
    payload: RagAskRequest,
    current_user: User = Depends(get_current_user),
    service: RagAskService = Depends(get_rag_ask_service),
) -> ApiResponse[RagAskRead]:
    result = await service.ask(current_user.id, payload.query, top_k=payload.top_k)
    return ApiResponse(
        data=RagAskRead(
            query=payload.query,
            answer=result.answer,
            grounded=result.grounded,
            model=result.model,
            sources=[RagMatchRead.from_vector_match(match) for match in result.matches],
        )
    )
