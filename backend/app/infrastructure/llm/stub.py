"""Deterministic stub LLM (``LLM_PROVIDER=stub``).

Runs the whole platform with **no model server and no network**: the demo
stack, and the end-to-end suite in CI, would otherwise need a ~4.7 GB Ollama
image and CPU inference too slow and too non-deterministic to assert against.

This is a first-class provider, not a test double smuggled into ``app/``: the
port exists precisely so a backend can be swapped by configuration, and a
zero-dependency one is the difference between "clone and see it work" and
"clone, pull 4.7 GB, wait".

**It does not think.** Replies are selected by inspecting the system prompt and
keyword-scanning the request, so they are structurally valid — a routing word,
a JSON plan, a cited answer — and completely fixed. E2E runs against it prove
the *wiring* (upload indexes, routes reach the right agent, citations render,
approvals pause and resume); they prove nothing about answer quality. Never
select it in a deployment meant to be useful.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from app.domain.interfaces.llm import ChatMessage, ChatRole, LLMResult
from app.platform.registry import register_provider

MODEL_NAME = "stub"

# Recognisable fingerprints of the catalogued system prompts. Matching on these
# rather than on prompt keys keeps the provider a pure LLMProvider -- it sees
# only messages, exactly like a real backend does.
_ROUTING_MARKER = "EXACTLY one word"
_PLANNER_MARKER = "planning specialist"
_EMAIL_CLASSIFY_MARKER = "You triage incoming business email"
_EMAIL_DRAFT_MARKER = "drafting a reply"
_CITED_MARKERS = ("numbered context excerpts", "numbered web sources")

_ROUTE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("plan", ("plan", "organise", "organize", "break down", "todo", "roadmap")),
    ("research", ("research", "look up", "latest", "news", "competitor", "market")),
    (
        "knowledge",
        ("document", "policy", "contract", "invoice", "handbook", "vacation", "our "),
    ),
)

_DEFAULT_PLAN = [
    {
        "title": "Clarify the goal",
        "description": "Write down the outcome and how it will be measured.",
        "priority": "high",
    },
    {
        "title": "Draft the plan",
        "description": "Outline the steps and their order.",
        "priority": "medium",
    },
    {
        "title": "Review and adjust",
        "description": "Check the plan against constraints and revise.",
        "priority": "low",
    },
]

_DEFAULT_CLASSIFICATION = {
    "intent": "question",
    "summary": "A question about the sender's account.",
    "entities": {},
}


@register_provider(kind="llm", name="stub")
class StubLLMProvider:
    """Fixed, structurally valid replies. No network, no model, no thought."""

    name = MODEL_NAME

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResult:
        system = _first(messages, ChatRole.SYSTEM)
        request = _last(messages, ChatRole.USER)
        content = self._reply(system, request)
        return LLMResult(
            content=content,
            model=MODEL_NAME,
            prompt_tokens=sum(len(message.content.split()) for message in messages),
            completion_tokens=len(content.split()),
            duration_ms=0,
        )

    def _reply(self, system: str, request: str) -> str:
        if _ROUTING_MARKER in system:
            return _route(request)
        if _PLANNER_MARKER in system:
            return json.dumps(_DEFAULT_PLAN)
        if _EMAIL_CLASSIFY_MARKER in system:
            return json.dumps(_DEFAULT_CLASSIFICATION)
        if _EMAIL_DRAFT_MARKER in system:
            return (
                "Thanks for getting in touch — I've noted your message and will "
                "follow up shortly."
            )
        if any(marker in system for marker in _CITED_MARKERS):
            # The caller only reaches a cited prompt when retrieval found
            # something, so a citation is always warranted here.
            return f"Based on the provided sources, {_echo(request)} [1]"
        return f"{_echo(request).capitalize()}"


def _route(request: str) -> str:
    """Pick a route the same way every time, from the request's keywords."""
    lowered = request.lower()
    for route, keywords in _ROUTE_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return route
    return "general"


def _echo(request: str) -> str:
    """A short, deterministic acknowledgement of the request."""
    trimmed = " ".join(request.split())[:160]
    return f"here is a stubbed response to: {trimmed}" if trimmed else "hello"


def _first(messages: Sequence[ChatMessage], role: ChatRole) -> str:
    return next((m.content for m in messages if m.role is role), "")


def _last(messages: Sequence[ChatMessage], role: ChatRole) -> str:
    return next((m.content for m in reversed(messages) if m.role is role), "")
