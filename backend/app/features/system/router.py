"""System endpoints: liveness health check and service metadata.

These endpoints are intentionally unversioned (not under ``/api/v1``) so that
orchestrators and load balancers can probe a stable path. Readiness checks for
downstream dependencies (database, vector store, LLM runtime) are added in the
milestones that introduce those dependencies.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from app.core.config import Settings, get_settings
from app.core.dependencies import get_database
from app.core.logging import get_logger
from app.domain.interfaces.database import DatabaseProvider
from app.features.system.schemas import HealthResponse, ReadinessResponse, RootResponse

logger = get_logger("app.system")

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def health() -> HealthResponse:
    """Report application liveness."""
    settings: Settings = get_settings()
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.environment.value,
    )


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness(
    response: Response,
    db: DatabaseProvider = Depends(get_database),
) -> ReadinessResponse:
    """Report readiness by probing downstream dependencies (currently the database)."""
    checks: dict[str, str] = {}
    healthy = True

    try:
        await db.health()
        checks["database"] = "ok"
    except Exception:  # noqa: BLE001 - report as unhealthy rather than 500
        logger.exception("readiness_check_failed", extra={"dependency": "database"})
        checks["database"] = "error"
        healthy = False

    response.status_code = (
        status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    return ReadinessResponse(status="ready" if healthy else "not_ready", checks=checks)


@router.get("/", response_model=RootResponse)
async def root() -> RootResponse:
    """Return basic service metadata and a pointer to the API docs."""
    settings: Settings = get_settings()
    return RootResponse(name=settings.app_name, version=settings.app_version, docs="/docs")
