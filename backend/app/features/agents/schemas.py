"""Request/response schemas for the agents feature."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.features.rag.schemas import RagMatchRead


class AgentAskRequest(BaseModel):
    """A request routed through the supervisor graph.

    Passing ``conversation_id`` continues an existing thread (prior turns are
    fed to the agents); omitting it starts a new conversation. With
    ``require_approval`` the drafted answer pauses for human review before it
    is committed to the conversation.
    """

    message: str = Field(min_length=1, max_length=4000)
    conversation_id: UUID | None = None
    require_approval: bool = False


class WebSourceRead(BaseModel):
    """A web citation from the research agent."""

    title: str
    url: str
    snippet: str


class AgentAskRead(BaseModel):
    """The outcome of an agent run.

    ``status`` is ``awaiting_approval`` when the drafted answer is paused for
    review — then ``approval_id`` is set and ``answer`` holds the draft.
    """

    conversation_id: UUID
    run_id: UUID
    status: Literal["completed", "awaiting_approval"]
    approval_id: UUID | None = None
    message: str
    answer: str
    agent: str
    grounded: bool
    model: str | None
    sources: list[RagMatchRead]
    web_sources: list[WebSourceRead] = []


class AgentInfoRead(BaseModel):
    """A registered agent, for introspection."""

    name: str
    description: str
