"""Aggregates all version-1 feature routers under a single ``APIRouter``.

Feature routers (auth, users, documents, rag, ...) are included here as they are
implemented in subsequent milestones. This is the single extension point for the
versioned API surface, keeping ``main.py`` free of feature-specific imports.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.features.agents.router import router as agents_router
from app.features.analytics.router import router as analytics_router
from app.features.approvals.router import router as approvals_router
from app.features.auth.router import router as auth_router
from app.features.conversations.router import router as conversations_router
from app.features.documents.router import router as documents_router
from app.features.notifications.router import router as notifications_router
from app.features.rag.router import router as rag_router
from app.features.scheduler.router import router as scheduler_router
from app.features.tasks.router import router as tasks_router
from app.features.users.router import router as users_router
from app.features.workflows.router import router as workflows_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(documents_router, prefix="/documents", tags=["documents"])
api_router.include_router(rag_router, prefix="/rag", tags=["rag"])
api_router.include_router(agents_router, prefix="/agents", tags=["agents"])
api_router.include_router(
    conversations_router, prefix="/conversations", tags=["conversations"]
)
api_router.include_router(workflows_router, prefix="/workflows", tags=["workflows"])
api_router.include_router(approvals_router, prefix="/approvals", tags=["approvals"])
api_router.include_router(
    notifications_router, prefix="/notifications", tags=["notifications"]
)
api_router.include_router(scheduler_router, prefix="/scheduler", tags=["scheduler"])
api_router.include_router(tasks_router, prefix="/tasks", tags=["tasks"])
api_router.include_router(analytics_router, prefix="/analytics", tags=["analytics"])
