"""Prompt templates as versioned, rendered artifacts.

Prompts are software: they get a key, a version, declared variables, and strict
rendering. Jinja2 runs with ``StrictUndefined`` so a template referencing a
variable the caller didn't supply raises at render time instead of silently
producing a prompt with a hole in it.

Versions are **immutable**. Iterating on a prompt means registering a new
version, never editing a registered one — that is what makes the ``prompt_key`` /
``prompt_version`` pair recorded on every ``AiExecution`` row reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from jinja2 import StrictUndefined, Template
from jinja2 import TemplateError as JinjaTemplateError

from app.core.exceptions import AppError


class PromptError(AppError):
    """Raised when a prompt cannot be resolved or rendered."""

    code = "PROMPT_ERROR"
    status_code = 422
    message = "Prompt could not be rendered"


@dataclass(frozen=True)
class PromptTemplate:
    """One immutable version of one prompt."""

    key: str
    version: int
    body: str
    variables: tuple[str, ...] = ()
    description: str = ""
    # Marks the version the registry hands out for `key` by default. Exactly one
    # active version per key is enforced at registration time.
    active: bool = True
    tags: tuple[str, ...] = field(default_factory=tuple)

    def render(self, **values: Any) -> str:
        """Render the template, requiring every declared variable."""
        missing = [name for name in self.variables if name not in values]
        if missing:
            raise PromptError(
                f"Prompt '{self.key}' v{self.version} is missing "
                f"variable(s): {', '.join(sorted(missing))}"
            )
        try:
            return Template(self.body, undefined=StrictUndefined).render(**values)
        except JinjaTemplateError as exc:
            raise PromptError(
                f"Prompt '{self.key}' v{self.version} failed to render: {exc}"
            ) from exc

    def describe(self) -> dict[str, Any]:
        """JSON-friendly description for the prompts API."""
        return {
            "key": self.key,
            "version": self.version,
            "description": self.description,
            "variables": list(self.variables),
            "active": self.active,
            "tags": list(self.tags),
            "body": self.body,
        }
