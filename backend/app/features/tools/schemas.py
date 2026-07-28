"""Request/response schemas for the tools feature."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolRead(BaseModel):
    """Marketplace description of one registered tool."""

    name: str
    description: str
    category: str
    permissions: list[str]
    dependencies: list[str]
    version: str
    origin: str
    tags: list[str]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


class ToolInvokeRequest(BaseModel):
    """Arguments for a tool call, validated against the tool's own input model."""

    args: dict[str, Any] = Field(default_factory=dict)


class ToolInvokeResponse(BaseModel):
    """Result of a tool call."""

    tool: str
    result: dict[str, Any]
