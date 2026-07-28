"""Tool marketplace HTTP endpoints (workspace-scoped)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.core.schemas import ApiResponse
from app.features.tools.dependencies import get_tool_context, get_tool_service
from app.features.tools.schemas import (
    ToolInvokeRequest,
    ToolInvokeResponse,
    ToolRead,
)
from app.features.tools.service import ToolService
from app.mcp.server import handle_rpc
from app.tools.context import ToolContext

router = APIRouter()


@router.get("", response_model=ApiResponse[list[ToolRead]])
async def list_tools(
    category: str | None = Query(default=None, max_length=50),
    service: ToolService = Depends(get_tool_service),
) -> ApiResponse[list[ToolRead]]:
    tools = service.list_tools(category=category)
    return ApiResponse(data=[ToolRead.model_validate(tool) for tool in tools])


@router.get("/categories", response_model=ApiResponse[list[str]])
async def list_categories(
    service: ToolService = Depends(get_tool_service),
) -> ApiResponse[list[str]]:
    return ApiResponse(data=service.categories())


@router.post("/{name}/invoke", response_model=ApiResponse[ToolInvokeResponse])
async def invoke_tool(
    name: str,
    payload: ToolInvokeRequest,
    service: ToolService = Depends(get_tool_service),
    context: ToolContext = Depends(get_tool_context),
) -> ApiResponse[ToolInvokeResponse]:
    result = await service.invoke(name, payload.args, context)
    return ApiResponse(data=ToolInvokeResponse(tool=name, result=result))


@router.post("/mcp")
async def mcp_endpoint(
    payload: dict[str, Any],
    context: ToolContext = Depends(get_tool_context),
) -> dict[str, Any]:
    """JSON-RPC 2.0 endpoint exposing native tools to external MCP clients.

    Returns the raw JSON-RPC envelope, not the platform's ApiResponse wrapper —
    MCP clients expect the protocol's own shape.
    """
    return await handle_rpc(payload, context)
