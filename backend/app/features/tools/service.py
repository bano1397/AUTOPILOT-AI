"""Tool marketplace use-cases: listing and invocation.

Resolution goes through the singleton ``tool_registry``, so a tool file dropped
into ``app/tools/`` (or adapted from an MCP server later) is listed and callable
with no change here.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.core.exceptions import NotFoundError, ValidationAppError
from app.domain.interfaces.tool import ToolMeta
from app.platform.registry import PluginNotFoundError, tool_registry
from app.tools.context import ToolContext


def _meta_of(target: type[Any]) -> ToolMeta:
    meta = getattr(target, "meta", None)
    if not isinstance(meta, ToolMeta):  # pragma: no cover - registry guards this
        raise ValidationAppError("Registered tool is missing its ToolMeta")
    return meta


class ToolService:
    """Reads the tool registry and executes tools against a context."""

    def list_tools(self, *, category: str | None = None) -> list[dict[str, Any]]:
        """Describe every registered tool, optionally filtered by category."""
        described = [_meta_of(entry.target).describe() for entry in tool_registry.entries()]
        if category is not None:
            described = [tool for tool in described if tool["category"] == category]
        return sorted(described, key=lambda tool: (tool["category"], tool["name"]))

    def categories(self) -> list[str]:
        return sorted({_meta_of(e.target).category for e in tool_registry.entries()})

    async def invoke(
        self, name: str, args: dict[str, Any], context: ToolContext
    ) -> dict[str, Any]:
        """Validate ``args`` against the tool's input model and run it."""
        try:
            target = tool_registry.get(name)
        except PluginNotFoundError as exc:
            raise NotFoundError(f"Tool '{name}' is not registered") from exc

        meta = _meta_of(target)
        try:
            parsed = meta.inputs.model_validate(args)
        except ValidationError as exc:
            raise ValidationAppError(
                f"Invalid arguments for tool '{name}': {exc.error_count()} error(s)"
            ) from exc

        tool = target(context)
        output = await tool.run(parsed)
        return dict(output.model_dump(mode="json"))
