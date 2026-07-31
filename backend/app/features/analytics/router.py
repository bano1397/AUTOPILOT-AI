"""Analytics HTTP endpoints (workspace-scoped)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.schemas import ApiResponse
from app.features.analytics.dependencies import get_analytics_service
from app.features.analytics.schemas import AnalyticsOverviewRead
from app.features.analytics.service import AnalyticsService
from app.features.users.dependencies import get_workspace_user
from app.features.users.models import User

router = APIRouter()


@router.get("/overview", response_model=ApiResponse[AnalyticsOverviewRead])
async def overview(
    days: int = Query(default=30, ge=1, le=90),
    workspace_user: User = Depends(get_workspace_user),
    service: AnalyticsService = Depends(get_analytics_service),
) -> ApiResponse[AnalyticsOverviewRead]:
    data = await service.overview(workspace_user.id, days=days)
    return ApiResponse(data=data)
