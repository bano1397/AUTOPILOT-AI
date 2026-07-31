"""RAG HTTP endpoints (workspace-scoped)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

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
            matches=[RagMatchRead.from_chunk(match) for match in matches],
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
            sources=[RagMatchRead.from_chunk(match) for match in result.matches],
        )
    )


@router.post("/ask/stream")
async def ask_documents_streaming(
    payload: RagAskRequest,
    workspace_user: User = Depends(get_workspace_user),
    service: RagAskService = Depends(get_rag_ask_service),
    preferences: PreferencesService = Depends(get_preferences_service),
) -> StreamingResponse:
    """Grounded answer, streamed as Server-Sent Events.

    Same retrieval, compression, and citations as ``POST /rag/ask`` — only the
    delivery differs. Time-to-first-token is what a user experiences as speed,
    and a four-second answer that starts rendering immediately reads as fast
    while the same answer delivered whole reads as broken.

    Frames: ``sources`` (once, first), then ``delta`` per token group, then
    ``done``. Errors after the first byte arrive as an ``error`` frame — the
    status line is long gone by then, so an HTTP code is not available.
    """
    top_k = payload.top_k or (await preferences.get()).default_top_k

    async def frames() -> AsyncIterator[str]:
        async for frame in service.ask_stream(
            workspace_user.id, payload.query, top_k=top_k
        ):
            # Indexed rather than destructured, so the tagged union narrows:
            # mypy then knows a "sources" frame carries chunks and a "delta"
            # frame carries text.
            if frame[0] == "sources":
                body: object = [
                    RagMatchRead.from_chunk(chunk).model_dump(mode="json")
                    for chunk in frame[1]
                ]
            else:
                body = frame[1]
            yield f"event: {frame[0]}\ndata: {json.dumps(body)}\n\n"

    return StreamingResponse(
        frames(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            # Tell nginx and friends not to buffer, which would defeat the
            # entire point by delivering the stream in one lump at the end.
            "X-Accel-Buffering": "no",
        },
    )
