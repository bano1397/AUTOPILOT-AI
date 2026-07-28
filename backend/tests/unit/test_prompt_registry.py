"""Unit tests for the prompt registry and template rendering."""

from __future__ import annotations

import pytest
from app.core.exceptions import NotFoundError
from app.platform.prompts import prompt_registry
from app.platform.prompts.registry import PromptRegistry
from app.platform.prompts.template import PromptError, PromptTemplate


def _template(**overrides: object) -> PromptTemplate:
    defaults: dict[str, object] = {
        "key": "test.prompt",
        "version": 1,
        "body": "Hello {{ name }}.",
        "variables": ("name",),
        "description": "greeting",
    }
    defaults.update(overrides)
    return PromptTemplate(**defaults)  # type: ignore[arg-type]


def test_render_substitutes_declared_variables() -> None:
    assert _template().render(name="Ada") == "Hello Ada."


def test_render_rejects_missing_declared_variable() -> None:
    with pytest.raises(PromptError, match="missing variable"):
        _template().render()


def test_render_rejects_undeclared_placeholder() -> None:
    """StrictUndefined: a hole in the prompt is an error, not an empty string."""
    template = _template(body="Hi {{ nickname }}.", variables=())

    with pytest.raises(PromptError, match="failed to render"):
        template.render()


def test_registry_returns_the_active_version() -> None:
    registry = PromptRegistry()
    registry.register(_template(version=1, active=False))
    registry.register(_template(version=2, body="v2 {{ name }}", active=True))

    assert registry.get("test.prompt").version == 2
    assert registry.get("test.prompt", 1).version == 1


def test_registry_rejects_duplicate_version() -> None:
    registry = PromptRegistry()
    registry.register(_template())

    with pytest.raises(PromptError, match="already registered"):
        registry.register(_template())


def test_registry_rejects_a_second_active_version() -> None:
    """Two active versions would make 'which prompt ran?' unanswerable."""
    registry = PromptRegistry()
    registry.register(_template(version=1))

    with pytest.raises(PromptError, match="already has an active version"):
        registry.register(_template(version=2))


def test_unknown_key_and_version_raise_not_found() -> None:
    registry = PromptRegistry()
    registry.register(_template())

    with pytest.raises(NotFoundError):
        registry.get("nope")
    with pytest.raises(NotFoundError):
        registry.get("test.prompt", 99)


def test_describe_exposes_body_and_metadata() -> None:
    described = _template(tags=("a",)).describe()

    assert described["key"] == "test.prompt"
    assert described["version"] == 1
    assert described["variables"] == ["name"]
    assert described["tags"] == ["a"]
    assert described["body"] == "Hello {{ name }}."


class TestCatalog:
    """The real catalog, as registered at import time."""

    def test_every_live_prompt_is_registered(self) -> None:
        assert {
            "rag.ask.system",
            "agent.supervisor.routing",
            "agent.general.system",
            "agent.research.system",
            "agent.planner.system",
        } <= set(prompt_registry.keys())

    def test_each_key_has_exactly_one_active_version(self) -> None:
        for key in prompt_registry.keys():
            active = [t for t in prompt_registry.versions(key) if t.active]
            assert len(active) == 1, f"{key} has {len(active)} active versions"

    def test_catalogued_bodies_render_without_variables(self) -> None:
        # The live prompts are static system messages; the per-request content is
        # assembled in code. Rendering must therefore need no variables.
        for key in prompt_registry.keys():
            assert prompt_registry.render(key)

    def test_routing_prompt_still_contains_its_routing_contract(self) -> None:
        body = prompt_registry.render("agent.supervisor.routing")

        for label in ("knowledge:", "research:", "plan:", "general:"):
            assert label in body
        assert "EXACTLY one" in body
