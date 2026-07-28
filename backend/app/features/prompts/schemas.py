"""Request/response schemas for the prompts feature."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PromptRead(BaseModel):
    """One registered prompt version."""

    key: str
    version: int
    description: str
    variables: list[str]
    active: bool
    tags: list[str]
    body: str


class PromptRenderRequest(BaseModel):
    """Variables for a preview render."""

    variables: dict[str, Any] = Field(default_factory=dict)
    version: int | None = Field(default=None, ge=1)


class PromptRenderResponse(BaseModel):
    key: str
    version: int
    rendered: str
