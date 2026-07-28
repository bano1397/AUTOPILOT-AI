"""Expose AutoPilot's native tools *as* an MCP server.

External MCP clients (Claude Desktop, other agents) can point at
``POST /api/v1/mcp`` and use this platform's retrieval, search, and task tools
over standard JSON-RPC. Only native tools are exposed — MCP-adapted tools are
excluded so this server never becomes a proxy hop back to another server.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.domain.interfaces.tool import ToolMeta
from app.mcp.protocol import JSONRPC_VERSION, PROTOCOL_VERSION
from app.platform.registry import tool_registry
from app.tools.context import ToolContext

logger = get_logger("app.mcp.server")

SERVER_INFO = {"name": "autopilot-ai", "version": "1.0.0"}

# JSON-RPC 2.0 reserved codes.
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


def _native_tools() -> list[tuple[str, type[Any], ToolMeta]]:
    exposed = []
    for entry in tool_registry.entries():
        meta = getattr(entry.target, "meta", None)
        if isinstance(meta, ToolMeta) and meta.origin == "native":
            exposed.append((entry.name, entry.target, meta))
    return sorted(exposed, key=lambda item: item[0])


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": JSONRPC_VERSION,
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def _ok(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result}


async def handle_rpc(payload: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    """Dispatch one JSON-RPC call against the native tool registry."""
    request_id = payload.get("id")
    method = payload.get("method")

    if method == "initialize":
        return _ok(
            request_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
            },
        )

    if method == "tools/list":
        return _ok(
            request_id,
            {
                "tools": [
                    {
                        "name": name,
                        "description": meta.description,
                        "inputSchema": meta.inputs.model_json_schema(),
                    }
                    for name, _target, meta in _native_tools()
                ]
            },
        )

    if method == "tools/call":
        params = payload.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(name, str) or not isinstance(arguments, dict):
            return _error(request_id, INVALID_PARAMS, "name and arguments are required")

        match = next((item for item in _native_tools() if item[0] == name), None)
        if match is None:
            return _error(request_id, METHOD_NOT_FOUND, f"Unknown tool '{name}'")

        _name, target, meta = match
        try:
            parsed = meta.inputs.model_validate(arguments)
        except Exception as exc:  # noqa: BLE001 - surfaced to the peer as JSON-RPC
            return _error(request_id, INVALID_PARAMS, f"Invalid arguments: {exc}")

        try:
            output = await target(context).run(parsed)
        except Exception as exc:  # noqa: BLE001 - tool failure is a protocol result
            logger.warning("mcp.tool_call_failed", extra={"tool": name, "error": str(exc)})
            return _ok(
                request_id,
                {
                    "isError": True,
                    "content": [{"type": "text", "text": str(exc)}],
                },
            )

        return _ok(
            request_id,
            {
                "isError": False,
                "structuredContent": output.model_dump(mode="json"),
                "content": [
                    {"type": "text", "text": output.model_dump_json()},
                ],
            },
        )

    return _error(request_id, METHOD_NOT_FOUND, f"Unknown method '{method}'")
