"""Dashboard HTTP endpoint: one read for the landing page."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.pagination import PaginationParams
from app.core.schemas import ApiResponse
from app.features.agents.schemas import AgentInfoRead
from app.features.agents.service import list_registered_agents
from app.features.analytics.dependencies import get_analytics_service
from app.features.analytics.service import AnalyticsService
from app.features.approvals.dependencies import get_approval_service
from app.features.approvals.schemas import ApprovalRead
from app.features.approvals.service import ApprovalService
from app.features.dashboard.schemas import DashboardRead
from app.features.users.dependencies import get_workspace_user
from app.features.users.models import User
from app.features.workflows.dependencies import get_workflow_query_service
from app.features.workflows.schemas import WorkflowRunRead
from app.features.workflows.service import WorkflowQueryService

router = APIRouter()

# The dashboard shows a preview, not the queue; the Approvals page pages.
_APPROVAL_PREVIEW = 5
_RUN_PREVIEW = 8


@router.get("", response_model=ApiResponse[DashboardRead])
async def dashboard(
    days: int = Query(default=30, ge=1, le=90),
    workspace_user: User = Depends(get_workspace_user),
    analytics: AnalyticsService = Depends(get_analytics_service),
    approvals: ApprovalService = Depends(get_approval_service),
    workflows: WorkflowQueryService = Depends(get_workflow_query_service),
) -> ApiResponse[DashboardRead]:
    """Everything the landing page needs, in one round trip.

    The page previously composed three separate calls client-side, which meant
    three round trips before anything rendered and three independent loading
    and error states for what a user reads as one screen. Aggregating here also
    keeps the numbers consistent: three calls can land either side of a write
    and show a dashboard that never existed at any single moment.

    This is a *read view* over existing services -- it holds no logic of its
    own, so there is nothing here to drift from the pages it summarises.
    """
    overview = await analytics.overview(workspace_user.id, days=days)
    pending, pending_total = await approvals.list_pending(
        workspace_user.id, PaginationParams(page=1, page_size=_APPROVAL_PREVIEW)
    )
    runs, _ = await workflows.list_runs(
        workspace_user.id, PaginationParams(page=1, page_size=_RUN_PREVIEW)
    )

    return ApiResponse(
        data=DashboardRead(
            analytics=overview,
            pending_approvals=[ApprovalRead.model_validate(a) for a in pending],
            pending_approval_count=pending_total,
            agents=[
                AgentInfoRead(name=name, description=description)
                for name, description in list_registered_agents()
            ],
            recent_runs=[WorkflowRunRead.model_validate(r) for r in runs],
        )
    )
