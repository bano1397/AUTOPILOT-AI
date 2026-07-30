"""Workflow HTTP endpoints (workspace-scoped)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi import status as http_status

from app.core.pagination import PaginationParams, build_page_meta, pagination_params
from app.core.schemas import ApiResponse
from app.features.users.dependencies import get_workspace_user
from app.features.users.models import User
from app.features.workflows.dependencies import (
    get_workflow_lifecycle_service,
    get_workflow_query_service,
)
from app.features.workflows.lifecycle import (
    WorkflowLifecycleService,
    available_agents,
)
from app.features.workflows.schemas import (
    AgentCatalogueRead,
    WorkflowCloneRequest,
    WorkflowDefinitionCreateRequest,
    WorkflowDefinitionDetailRead,
    WorkflowDefinitionRead,
    WorkflowRunDetailRead,
    WorkflowRunRead,
    WorkflowStepRead,
    WorkflowVersionCreateRequest,
    WorkflowVersionRead,
)
from app.features.workflows.service import WorkflowQueryService

router = APIRouter()


@router.get("/runs", response_model=ApiResponse[list[WorkflowRunRead]])
async def list_runs(
    pagination: PaginationParams = Depends(pagination_params),
    workspace_user: User = Depends(get_workspace_user),
    service: WorkflowQueryService = Depends(get_workflow_query_service),
) -> ApiResponse[list[WorkflowRunRead]]:
    items, total = await service.list_runs(workspace_user.id, pagination)
    return ApiResponse(
        data=[WorkflowRunRead.model_validate(item) for item in items],
        meta=build_page_meta(pagination, total).model_dump(),
    )


@router.get("/runs/{run_id}", response_model=ApiResponse[WorkflowRunDetailRead])
async def get_run(
    run_id: UUID,
    workspace_user: User = Depends(get_workspace_user),
    service: WorkflowQueryService = Depends(get_workflow_query_service),
) -> ApiResponse[WorkflowRunDetailRead]:
    run, steps = await service.get_run(workspace_user.id, run_id)
    return ApiResponse(
        data=WorkflowRunDetailRead(
            run=WorkflowRunRead.model_validate(run),
            input=run.input,
            output=run.output,
            steps=[WorkflowStepRead.model_validate(step) for step in steps],
        )
    )


# --- Definitions & versions (blueprint §20) ---------------------------------
# These endpoints are open like the rest of the API (docs/COMPLETION_PLAN.md §3),
# and they change how every agent request is routed. That is a deliberate
# consequence of having no roles, and it is called out in the README's
# no-authentication warning rather than papered over with a fake check.


@router.get("/agents-catalogue", response_model=ApiResponse[AgentCatalogueRead])
async def agents_catalogue() -> ApiResponse[AgentCatalogueRead]:
    """Agent names a ``graph_spec`` may reference on this deployment."""
    return ApiResponse(data=AgentCatalogueRead(agents=available_agents()))


@router.get("/definitions", response_model=ApiResponse[list[WorkflowDefinitionRead]])
async def list_definitions(
    pagination: PaginationParams = Depends(pagination_params),
    workspace_user: User = Depends(get_workspace_user),
    service: WorkflowLifecycleService = Depends(get_workflow_lifecycle_service),
) -> ApiResponse[list[WorkflowDefinitionRead]]:
    items, total = await service.list_definitions(pagination)
    return ApiResponse(
        data=[WorkflowDefinitionRead.model_validate(item) for item in items],
        meta=build_page_meta(pagination, total).model_dump(),
    )


@router.post(
    "/definitions",
    response_model=ApiResponse[WorkflowDefinitionDetailRead],
    status_code=http_status.HTTP_201_CREATED,
)
async def create_definition(
    payload: WorkflowDefinitionCreateRequest,
    workspace_user: User = Depends(get_workspace_user),
    service: WorkflowLifecycleService = Depends(get_workflow_lifecycle_service),
) -> ApiResponse[WorkflowDefinitionDetailRead]:
    spec = service.parse_spec(payload.graph_spec)
    definition, version = await service.create_definition(
        payload.name, payload.description, spec
    )
    return ApiResponse(data=_detail(definition, [version]))


@router.get(
    "/definitions/{definition_id}",
    response_model=ApiResponse[WorkflowDefinitionDetailRead],
)
async def get_definition(
    definition_id: UUID,
    workspace_user: User = Depends(get_workspace_user),
    service: WorkflowLifecycleService = Depends(get_workflow_lifecycle_service),
) -> ApiResponse[WorkflowDefinitionDetailRead]:
    definition = await service.get_definition(definition_id)
    versions = await service.list_versions(definition_id)
    return ApiResponse(data=_detail(definition, list(versions)))


@router.post(
    "/definitions/{definition_id}/versions",
    response_model=ApiResponse[WorkflowVersionRead],
    status_code=http_status.HTTP_201_CREATED,
)
async def add_version(
    definition_id: UUID,
    payload: WorkflowVersionCreateRequest,
    workspace_user: User = Depends(get_workspace_user),
    service: WorkflowLifecycleService = Depends(get_workflow_lifecycle_service),
) -> ApiResponse[WorkflowVersionRead]:
    """Append an immutable version. There is no update endpoint by design."""
    spec = service.parse_spec(payload.graph_spec)
    version = await service.add_version(
        definition_id, spec, notes=payload.notes, activate=payload.activate
    )
    return ApiResponse(data=WorkflowVersionRead.model_validate(version))


@router.post(
    "/versions/{version_id}/activate",
    response_model=ApiResponse[WorkflowVersionRead],
)
async def activate_version(
    version_id: UUID,
    workspace_user: User = Depends(get_workspace_user),
    service: WorkflowLifecycleService = Depends(get_workflow_lifecycle_service),
) -> ApiResponse[WorkflowVersionRead]:
    """Make this version live. Activating an older one *is* the rollback."""
    version = await service.activate_version(version_id)
    return ApiResponse(data=WorkflowVersionRead.model_validate(version))


@router.get(
    "/versions/{version_id}/runs", response_model=ApiResponse[list[WorkflowRunRead]]
)
async def runs_for_version(
    version_id: UUID,
    pagination: PaginationParams = Depends(pagination_params),
    workspace_user: User = Depends(get_workspace_user),
    service: WorkflowLifecycleService = Depends(get_workflow_lifecycle_service),
) -> ApiResponse[list[WorkflowRunRead]]:
    """Execution history for one version."""
    items, total = await service.runs_for_version(version_id, pagination)
    return ApiResponse(
        data=[WorkflowRunRead.model_validate(item) for item in items],
        meta=build_page_meta(pagination, total).model_dump(),
    )


@router.post(
    "/definitions/{definition_id}/clone",
    response_model=ApiResponse[WorkflowDefinitionDetailRead],
    status_code=http_status.HTTP_201_CREATED,
)
async def clone_definition(
    definition_id: UUID,
    payload: WorkflowCloneRequest,
    workspace_user: User = Depends(get_workspace_user),
    service: WorkflowLifecycleService = Depends(get_workflow_lifecycle_service),
) -> ApiResponse[WorkflowDefinitionDetailRead]:
    """Fork a definition, seeding v1 from the source's active spec."""
    definition, version = await service.clone_definition(
        definition_id, payload.name, description=payload.description
    )
    return ApiResponse(data=_detail(definition, [version]))


def _detail(definition: Any, versions: list[Any]) -> WorkflowDefinitionDetailRead:
    reads = [WorkflowVersionRead.model_validate(v) for v in versions]
    return WorkflowDefinitionDetailRead(
        definition=WorkflowDefinitionRead.model_validate(definition),
        versions=reads,
        active_version=next((v for v in reads if v.is_active), None),
    )
