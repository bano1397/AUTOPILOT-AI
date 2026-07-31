"""Response schema for the dashboard aggregate."""

from __future__ import annotations

from pydantic import BaseModel

from app.features.agents.schemas import AgentInfoRead
from app.features.analytics.schemas import AnalyticsOverviewRead
from app.features.approvals.schemas import ApprovalRead
from app.features.workflows.schemas import WorkflowRunRead


class DashboardRead(BaseModel):
    """Everything the landing page renders, in one response.

    Composed of the existing feature schemas rather than a flattened copy: the
    dashboard is a *view* over them, and duplicating the shapes here would mean
    two places to update whenever any of them changes.
    """

    analytics: AnalyticsOverviewRead
    pending_approvals: list[ApprovalRead]
    pending_approval_count: int
    agents: list[AgentInfoRead]
    recent_runs: list[WorkflowRunRead]
