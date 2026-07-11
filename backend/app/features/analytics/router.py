"""Analytics HTTP endpoints (authenticated, owner-scoped)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session
from app.core.schemas import ApiResponse
from app.features.analytics.schemas import AnalyticsOverviewRead
from app.features.analytics.service import AnalyticsService
from app.features.auth.dependencies import get_current_user
from app.features.users.models import User

router = APIRouter()


def get_analytics_service(
    session: AsyncSession = Depends(get_db_session),
) -> AnalyticsService:
    return AnalyticsService(session)


@router.get("/overview", response_model=ApiResponse[AnalyticsOverviewRead])
async def overview(
    days: int = Query(default=30, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    service: AnalyticsService = Depends(get_analytics_service),
) -> ApiResponse[AnalyticsOverviewRead]:
    data = await service.overview(current_user.id, days=days)
    return ApiResponse(data=data)
