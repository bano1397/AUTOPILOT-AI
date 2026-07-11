"""Response schemas for the system feature."""

from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Liveness response returned by ``GET /health``."""

    status: str
    app: str
    version: str
    environment: str


class RootResponse(BaseModel):
    """Service metadata returned by ``GET /``."""

    name: str
    version: str
    docs: str


class ReadinessResponse(BaseModel):
    """Readiness response returned by ``GET /health/ready``."""

    status: str
    checks: dict[str, str]
