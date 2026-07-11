"""Response schemas for the analytics feature."""

from __future__ import annotations

from pydantic import BaseModel


class TotalsRead(BaseModel):
    """Windowed AI-usage totals for the caller."""

    executions: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    avg_duration_ms: int
    errors: int
    error_rate: float


class FeatureStatRead(BaseModel):
    feature: str
    executions: int
    total_tokens: int
    cost_usd: float


class ModelStatRead(BaseModel):
    model: str
    executions: int
    total_tokens: int
    cost_usd: float


class TimeseriesPointRead(BaseModel):
    date: str  # YYYY-MM-DD (UTC)
    executions: int
    total_tokens: int
    cost_usd: float


class StatusCountRead(BaseModel):
    status: str
    count: int


class EntityCountsRead(BaseModel):
    """Current inventory counts (all-time, not windowed)."""

    workflow_runs: list[StatusCountRead]
    documents_indexed: int
    tasks: list[StatusCountRead]


class AnalyticsOverviewRead(BaseModel):
    days: int
    totals: TotalsRead
    by_feature: list[FeatureStatRead]
    by_model: list[ModelStatRead]
    timeseries: list[TimeseriesPointRead]
    entities: EntityCountsRead
