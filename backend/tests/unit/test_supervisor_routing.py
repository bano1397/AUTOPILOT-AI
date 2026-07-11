"""Unit tests for supervisor routing (classifier parsing + fast path)."""

from __future__ import annotations

from app.agents.supervisor.supervisor import fast_route, parse_route


def test_parse_route_precedence_and_fallback() -> None:
    assert parse_route("research") == "research"
    assert parse_route(" PLAN ") == "planner"
    assert parse_route("general") == "general"
    assert parse_route("knowledge") == "knowledge"
    # Garbage falls back to knowledge (the safe side).
    assert parse_route("hmm, maybe the docs one??") == "knowledge"


def test_fast_route_matches_explicit_commands() -> None:
    assert fast_route("Research the competitors of OpenAI") == "research"
    assert fast_route("look up the latest FastAPI version") == "research"
    assert fast_route("Can you search the web for reviews?") == "research"
    assert fast_route("Plan the launch of our newsletter") == "planner"
    assert fast_route("break down the redesign into tasks") == "planner"


def test_fast_route_ignores_non_commands() -> None:
    # Words appearing mid-sentence must not trigger the fast path.
    assert fast_route("what does our research policy say?") is None
    assert fast_route("do we have a floor plan document?") is None
    assert fast_route("hello there") is None
