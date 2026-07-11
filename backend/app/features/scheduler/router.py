"""Scheduler HTTP endpoints (admin-only)."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, Request

from app.core.schemas import ApiResponse, MessageResponse
from app.features.auth.dependencies import require_admin
from app.features.scheduler.manager import SchedulerManager
from app.features.scheduler.schemas import JobRunRead, ScheduledJobRead

router = APIRouter(dependencies=[Depends(require_admin)])


def get_scheduler_manager(request: Request) -> SchedulerManager:
    return cast(SchedulerManager, request.app.state.scheduler)


@router.get("/jobs", response_model=ApiResponse[list[ScheduledJobRead]])
async def list_jobs(
    manager: SchedulerManager = Depends(get_scheduler_manager),
) -> ApiResponse[list[ScheduledJobRead]]:
    return ApiResponse(
        data=[
            ScheduledJobRead(
                id=info.id,
                name=info.name,
                description=info.description,
                next_run_at=info.next_run_at,
                paused=info.paused,
            )
            for info in manager.list_jobs()
        ]
    )


@router.post("/jobs/{job_id}/run", response_model=ApiResponse[JobRunRead])
async def run_job(
    job_id: str,
    manager: SchedulerManager = Depends(get_scheduler_manager),
) -> ApiResponse[JobRunRead]:
    summary = await manager.run_job(job_id)
    return ApiResponse(data=JobRunRead(job_id=job_id, summary=summary))


@router.post("/jobs/{job_id}/pause", response_model=ApiResponse[MessageResponse])
async def pause_job(
    job_id: str,
    manager: SchedulerManager = Depends(get_scheduler_manager),
) -> ApiResponse[MessageResponse]:
    manager.pause_job(job_id)
    return ApiResponse(data=MessageResponse(message=f"Job '{job_id}' paused"))


@router.post("/jobs/{job_id}/resume", response_model=ApiResponse[MessageResponse])
async def resume_job(
    job_id: str,
    manager: SchedulerManager = Depends(get_scheduler_manager),
) -> ApiResponse[MessageResponse]:
    manager.resume_job(job_id)
    return ApiResponse(data=MessageResponse(message=f"Job '{job_id}' resumed"))
