"""The prompt registry: resolve a key to its active version and render it.

Templates are code-defined (see :mod:`app.platform.prompts.catalog`), which keeps
one source of truth and makes every version reviewable in the diff. A
database-backed authoring UI with scored evaluation and version promotion is
deliberately **not** built — see ``docs/COMPLETION_PLAN.md`` §6 — but the
registry's shape (keys, immutable versions, declared variables) is what that
would plug into.
"""

from __future__ import annotations

from typing import Any

from app.core.exceptions import NotFoundError
from app.platform.prompts.template import PromptError, PromptTemplate


class PromptRegistry:
    """Keyed collection of immutable prompt versions."""

    def __init__(self) -> None:
        self._by_key: dict[str, dict[int, PromptTemplate]] = {}

    def register(self, template: PromptTemplate) -> PromptTemplate:
        """Register one version. Duplicate (key, version) pairs are rejected."""
        versions = self._by_key.setdefault(template.key, {})
        if template.version in versions:
            raise PromptError(
                f"Prompt '{template.key}' v{template.version} is already registered"
            )
        if template.active:
            clashing = [v for v, t in versions.items() if t.active]
            if clashing:
                raise PromptError(
                    f"Prompt '{template.key}' already has an active version "
                    f"(v{clashing[0]}); register the new one with active=False "
                    f"or deactivate the old one"
                )
        versions[template.version] = template
        return template

    def get(self, key: str, version: int | None = None) -> PromptTemplate:
        """Return a specific version, or the active one when ``version`` is None."""
        versions = self._by_key.get(key)
        if not versions:
            raise NotFoundError(f"Prompt '{key}' is not registered")
        if version is not None:
            template = versions.get(version)
            if template is None:
                raise NotFoundError(f"Prompt '{key}' has no version {version}")
            return template
        for template in versions.values():
            if template.active:
                return template
        raise NotFoundError(f"Prompt '{key}' has no active version")

    def render(self, key: str, *, version: int | None = None, **values: Any) -> str:
        return self.get(key, version).render(**values)

    def keys(self) -> list[str]:
        return sorted(self._by_key)

    def versions(self, key: str) -> list[PromptTemplate]:
        versions = self._by_key.get(key)
        if not versions:
            raise NotFoundError(f"Prompt '{key}' is not registered")
        return [versions[v] for v in sorted(versions)]

    def all_templates(self) -> list[PromptTemplate]:
        return [t for key in self.keys() for t in self.versions(key)]

    def clear(self) -> None:
        """Drop all registrations (tests only)."""
        self._by_key.clear()


# Singleton, populated by importing the catalog.
prompt_registry = PromptRegistry()


def register_prompt(template: PromptTemplate) -> PromptTemplate:
    """Register ``template`` on the singleton registry."""
    return prompt_registry.register(template)
