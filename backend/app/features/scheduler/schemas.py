"""Response schemas for the scheduler feature."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ScheduledJobRead(BaseModel):
    """A registered recurring job."""

    id: str
    name: str
    description: str
    next_run_at: datetime | None
    paused: bool


class JobRunRead(BaseModel):
    """Result of running a job on demand."""

    job_id: str
    summary: dict[str, Any]
