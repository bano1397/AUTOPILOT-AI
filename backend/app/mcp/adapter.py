"""Adapt a remote MCP tool to the native :class:`Tool` contract.

The point of the adapter: agents select tools by capability, not origin, so an
MCP tool must be indistinguishable from a native one at the call site. The only
visible difference is ``ToolMeta.origin == "mcp"``, which the marketplace surfaces
as a badge.

Input models are synthesized from the server's advertised JSON Schema. The
mapping covers the scalar/array/object types MCP servers actually publish; an
unrecognized type falls back to ``Any`` rather than rejecting the tool, so a
server using an exotic schema is still callable.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, Field, create_model

from app.core.logging import get_logger
from app.domain.interfaces.tool import ToolMeta
from app.mcp.client import MCPClient
from app.mcp.protocol import McpToolDescriptor

logger = get_logger("app.mcp.adapter")

_JSON_TO_PYTHON: dict[str, Any] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


class McpToolResult(BaseModel):
    """Envelope for whatever a remote tool returns.

    Remote payloads have no schema we control, so the result is carried as data
    under one key instead of being spread into typed fields we cannot guarantee.
    """

    result: dict[str, Any] = Field(default_factory=dict)


def build_input_model(descriptor: McpToolDescriptor) -> type[BaseModel]:
    """Create a pydantic model from a remote tool's input JSON Schema."""
    properties = descriptor.input_schema.get("properties")
    if not isinstance(properties, dict) or not properties:
        # Schema-less tool: accept anything, validate nothing we can't check.
        return create_model(f"{descriptor.name}_Input", __base__=BaseModel)

    required = set(descriptor.input_schema.get("required") or [])
    fields: dict[str, Any] = {}
    for key, schema in properties.items():
        json_type = schema.get("type") if isinstance(schema, dict) else None
        python_type = _JSON_TO_PYTHON.get(str(json_type), Any)
        description = (
            str(schema.get("description", "")) if isinstance(schema, dict) else ""
        )
        if key in required:
            fields[key] = (python_type, Field(description=description or None))
        else:
            fields[key] = (
                python_type | None if python_type is not Any else Any,
                Field(default=None, description=description or None),
            )
    return create_model(f"{descriptor.name}_Input", __base__=BaseModel, **fields)


def build_adapter(
    client: MCPClient, descriptor: McpToolDescriptor, *, name_prefix: str = ""
) -> type[Any]:
    """Return a Tool-shaped class wrapping one remote MCP tool."""
    input_model = build_input_model(descriptor)
    tool_name = f"{name_prefix}{descriptor.name}"

    tool_meta = ToolMeta(
        name=tool_name,
        description=descriptor.description or f"MCP tool '{descriptor.name}'",
        category="mcp",
        inputs=input_model,
        outputs=McpToolResult,
        # Declarative only, as for native tools — nothing enforces it (§3).
        permissions=("mcp:call",),
        dependencies=(f"MCPServer:{client.name}",),
        version="1.0.0",
        origin="mcp",
        tags=("mcp", client.name),
    )

    class MCPToolAdapter:
        """Calls a remote MCP tool through the registered client."""

        # Declared here, assigned after the class is created: a class body does
        # not close over the enclosing function's scope, so `= tool_meta` inside
        # it would raise NameError.
        meta: ClassVar[ToolMeta]

        def __init__(self, context: Any) -> None:
            # Accepts a ToolContext for signature parity with native tools; the
            # remote server holds its own state, so the context is unused.
            self._context = context

        async def run(self, args: BaseModel) -> McpToolResult:
            arguments = {
                key: value
                for key, value in args.model_dump(mode="json").items()
                if value is not None
            }
            payload = await client.call_tool(descriptor.name, arguments)
            return McpToolResult(result=payload)

    MCPToolAdapter.meta = tool_meta
    MCPToolAdapter.__name__ = f"MCPToolAdapter_{tool_name}"
    MCPToolAdapter.__qualname__ = MCPToolAdapter.__name__
    return MCPToolAdapter
