"""RAG HTTP endpoints (workspace-scoped)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.schemas import ApiResponse
from app.features.preferences.dependencies import get_preferences_service
from app.features.preferences.service import PreferencesService
from app.features.rag.dependencies import get_rag_ask_service, get_rag_service
from app.features.rag.schemas import (
    RagAskRead,
    RagAskRequest,
    RagMatchRead,
    RagQueryRead,
    RagQueryRequest,
)
from app.features.rag.service import RagAskService, RagService
from app.features.users.dependencies import get_workspace_user
from app.features.users.models import User

router = APIRouter()


@router.post("/query", response_model=ApiResponse[RagQueryRead])
async def query_documents(
    payload: RagQueryRequest,
    workspace_user: User = Depends(get_workspace_user),
    service: RagService = Depends(get_rag_service),
    preferences: PreferencesService = Depends(get_preferences_service),
) -> ApiResponse[RagQueryRead]:
    top_k = payload.top_k or (await preferences.get()).default_top_k
    matches = await service.query(workspace_user.id, payload.query, top_k=top_k)
    return ApiResponse(
        data=RagQueryRead(
            query=payload.query,
            matches=[RagMatchRead.from_vector_match(match) for match in matches],
        )
    )


@router.post("/ask", response_model=ApiResponse[RagAskRead])
async def ask_documents(
    payload: RagAskRequest,
    workspace_user: User = Depends(get_workspace_user),
    service: RagAskService = Depends(get_rag_ask_service),
    preferences: PreferencesService = Depends(get_preferences_service),
) -> ApiResponse[RagAskRead]:
    top_k = payload.top_k or (await preferences.get()).default_top_k
    result = await service.ask(workspace_user.id, payload.query, top_k=top_k)
    return ApiResponse(
        data=RagAskRead(
            query=payload.query,
            answer=result.answer,
            grounded=result.grounded,
            model=result.model,
            sources=[RagMatchRead.from_vector_match(match) for match in result.matches],
        )
    )
