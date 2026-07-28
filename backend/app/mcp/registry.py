"""MCP server definitions and startup discovery.

Servers come from configuration only — ``MCP_SERVERS`` as a JSON array — which is
the allow-list. Discovery is failure-isolated: an unreachable or malformed server
logs and is skipped so the platform still boots, exactly like the notification
channels.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger
from app.mcp.adapter import build_adapter
from app.mcp.client import HttpMCPClient, MCPClient, StdioMCPClient
from app.platform.registry import DuplicateRegistrationError, tool_registry

logger = get_logger("app.mcp.registry")

# Remote tool names are namespaced so they can never shadow a native tool.
NAME_PREFIX = "mcp__"


@dataclass(frozen=True)
class McpServerDefinition:
    """One configured MCP server."""

    name: str
    transport: str  # "http" | "stdio"
    url: str | None = None
    command: str | None = None
    args: tuple[str, ...] = ()
    headers: dict[str, str] | None = None

    def build_client(self) -> MCPClient:
        if self.transport == "http":
            if not self.url:
                raise ValueError(f"MCP server '{self.name}' (http) requires a url")
            return HttpMCPClient(self.name, self.url, headers=self.headers)
        if self.transport == "stdio":
            if not self.command:
                raise ValueError(f"MCP server '{self.name}' (stdio) requires a command")
            return StdioMCPClient(self.name, self.command, list(self.args))
        raise ValueError(
            f"MCP server '{self.name}' has unknown transport '{self.transport}'"
        )


def parse_server_definitions(raw: str | None) -> list[McpServerDefinition]:
    """Parse the ``MCP_SERVERS`` JSON array. Malformed config yields no servers."""
    if not raw or not raw.strip():
        return []
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("mcp.config_invalid_json")
        return []
    if not isinstance(decoded, list):
        logger.warning("mcp.config_not_a_list")
        return []

    definitions: list[McpServerDefinition] = []
    for entry in decoded:
        if not isinstance(entry, dict) or not entry.get("name"):
            logger.warning("mcp.config_entry_skipped", extra={"entry": str(entry)[:200]})
            continue
        headers = entry.get("headers")
        definitions.append(
            McpServerDefinition(
                name=str(entry["name"]),
                transport=str(entry.get("transport", "http")),
                url=entry.get("url"),
                command=entry.get("command"),
                args=tuple(str(arg) for arg in entry.get("args", [])),
                headers=dict(headers) if isinstance(headers, dict) else None,
            )
        )
    return definitions


async def register_server_tools(
    definition: McpServerDefinition, *, client: MCPClient | None = None
) -> list[str]:
    """Connect to one server and register its tools. Returns the names added."""
    peer = client or definition.build_client()
    descriptors = await peer.list_tools()

    registered: list[str] = []
    for descriptor in descriptors:
        adapter = build_adapter(peer, descriptor, name_prefix=NAME_PREFIX)
        try:
            tool_registry.register(adapter.meta.name, adapter)
        except DuplicateRegistrationError:
            # Two servers advertising the same tool name: first wins, loudly.
            logger.warning(
                "mcp.tool_name_conflict",
                extra={"server": definition.name, "tool": adapter.meta.name},
            )
            continue
        registered.append(adapter.meta.name)
    logger.info(
        "mcp.server_registered",
        extra={"server": definition.name, "tools": len(registered)},
    )
    return registered


async def discover_mcp_tools(raw_config: str | None) -> dict[str, Any]:
    """Register every configured server's tools; never raises."""
    summary: dict[str, Any] = {"servers": 0, "tools": 0, "failed": []}
    for definition in parse_server_definitions(raw_config):
        try:
            names = await register_server_tools(definition)
        except Exception as exc:  # noqa: BLE001 - one bad server must not block boot
            logger.warning(
                "mcp.server_failed",
                extra={"server": definition.name, "error": str(exc)},
            )
            summary["failed"].append(definition.name)
            continue
        summary["servers"] += 1
        summary["tools"] += len(names)
    return summary
