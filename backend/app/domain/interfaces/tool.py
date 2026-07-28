"""Tool contract and metadata (port).

A tool is a capability an agent can invoke: typed input, typed output, declared
dependencies and permissions. Tools self-register with the ``tool_registry`` via
``@register_tool`` and are auto-discovered by the plugin scanner, so adding one
means adding a file — never editing a dispatch table (blueprint §19).

**Permissions are declarative.** There is no authentication or role model in this
platform (``docs/COMPLETION_PLAN.md`` §3), so nothing enforces
:attr:`ToolMeta.permissions` today. The field is kept because it documents what a
tool touches, drives marketplace filtering, and is the single enforcement point
if accounts are ever added. It is deliberately *not* wired to a checker that
would always pass — a permission gate that never denies is worse than none,
because it reads like protection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Protocol, runtime_checkable

from pydantic import BaseModel


@dataclass(frozen=True)
class ToolMeta:
    """Marketplace metadata every tool carries."""

    name: str
    description: str
    category: str
    inputs: type[BaseModel]
    outputs: type[BaseModel]
    permissions: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    version: str = "1.0.0"
    # "native" for tools implemented in this codebase; "mcp" for tools adapted
    # from an external MCP server. Agents select by capability, not origin.
    origin: str = "native"
    tags: tuple[str, ...] = field(default_factory=tuple)

    def describe(self) -> dict[str, Any]:
        """JSON-friendly description, including the input/output JSON schemas."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "permissions": list(self.permissions),
            "dependencies": list(self.dependencies),
            "version": self.version,
            "origin": self.origin,
            "tags": list(self.tags),
            "input_schema": self.inputs.model_json_schema(),
            "output_schema": self.outputs.model_json_schema(),
        }


@runtime_checkable
class Tool(Protocol):
    """Contract every tool implements."""

    meta: ClassVar[ToolMeta]

    async def run(self, args: BaseModel) -> BaseModel:
        """Execute the tool against validated ``args`` and return its output."""
        ...
