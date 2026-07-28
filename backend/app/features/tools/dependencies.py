"""Dependency providers for the tools feature."""

from __future__ import annotations

from fastapi import Depends, Request

from app.features.tools.service import ToolService
from app.features.users.dependencies import get_workspace_user
from app.features.users.models import User
from app.tools.context import ToolContext


def get_tool_service() -> ToolService:
    return ToolService()


def get_tool_context(
    request: Request,
    workspace_user: User = Depends(get_workspace_user),
) -> ToolContext:
    """Bundle the providers on ``app.state`` for one tool invocation."""
    state = request.app.state
    return ToolContext(
        user_id=workspace_user.id,
        db=state.db,
        embeddings=state.embeddings,
        vector_store=state.vector_store,
        search=state.search,
    )
