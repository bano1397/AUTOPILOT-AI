"""Prompt registry HTTP endpoints.

Read-only introspection plus a preview render. Prompts are code-defined, so
there is no create/update endpoint by design — a new version is a code change,
reviewable in the diff (see ``docs/COMPLETION_PLAN.md`` §6).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.schemas import ApiResponse
from app.features.prompts.schemas import (
    PromptRead,
    PromptRenderRequest,
    PromptRenderResponse,
)
from app.platform.prompts import prompt_registry

router = APIRouter()


@router.get("", response_model=ApiResponse[list[PromptRead]])
async def list_prompts() -> ApiResponse[list[PromptRead]]:
    templates = prompt_registry.all_templates()
    return ApiResponse(
        data=[PromptRead.model_validate(t.describe()) for t in templates]
    )


@router.get("/{key}", response_model=ApiResponse[list[PromptRead]])
async def get_prompt_versions(key: str) -> ApiResponse[list[PromptRead]]:
    versions = prompt_registry.versions(key)
    return ApiResponse(
        data=[PromptRead.model_validate(t.describe()) for t in versions]
    )


@router.post("/{key}/render", response_model=ApiResponse[PromptRenderResponse])
async def render_prompt(
    key: str, payload: PromptRenderRequest
) -> ApiResponse[PromptRenderResponse]:
    template = prompt_registry.get(key, payload.version)
    return ApiResponse(
        data=PromptRenderResponse(
            key=template.key,
            version=template.version,
            rendered=template.render(**payload.variables),
        )
    )
