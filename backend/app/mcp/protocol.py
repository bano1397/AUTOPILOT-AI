"""Minimal JSON-RPC 2.0 framing for the Model Context Protocol.

MCP is JSON-RPC 2.0 over a transport (stdio or HTTP). Only three methods are
needed to consume a server's tools — ``initialize``, ``tools/list``,
``tools/call`` — so the wire format is implemented directly rather than pulling
in the SDK, consistent with the Ollama/Chroma/S3 providers (``docs/PROJECT_ANALYSIS.md``
§7 decision 7). Every field this module reads is asserted in the unit tests.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

PROTOCOL_VERSION = "2025-06-18"
JSONRPC_VERSION = "2.0"


class McpProtocolError(Exception):
    """Raised when a peer returns a malformed or error response."""


@dataclass(frozen=True)
class McpToolDescriptor:
    """A tool as advertised by a remote MCP server."""

    name: str
    description: str
    input_schema: dict[str, Any]


def request(method: str, params: dict[str, Any] | None = None, *, id: int = 1) -> dict[str, Any]:
    """Build a JSON-RPC request envelope."""
    payload: dict[str, Any] = {"jsonrpc": JSONRPC_VERSION, "id": id, "method": method}
    if params is not None:
        payload["params"] = params
    return payload


def result_of(response: dict[str, Any]) -> dict[str, Any]:
    """Return a response's ``result``, converting a JSON-RPC error into an exception."""
    if "error" in response:
        error = response["error"] or {}
        raise McpProtocolError(
            f"MCP error {error.get('code', '?')}: {error.get('message', 'unknown')}"
        )
    result = response.get("result")
    if not isinstance(result, dict):
        raise McpProtocolError("MCP response has no result object")
    return result


def parse_tools(result: dict[str, Any]) -> list[McpToolDescriptor]:
    """Parse a ``tools/list`` result. Unnamed entries are skipped, not guessed at."""
    tools: list[McpToolDescriptor] = []
    for entry in result.get("tools", []):
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            continue
        schema = entry.get("inputSchema") or entry.get("input_schema") or {}
        tools.append(
            McpToolDescriptor(
                name=name,
                description=str(entry.get("description") or ""),
                input_schema=schema if isinstance(schema, dict) else {},
            )
        )
    return tools


def parse_call_result(result: dict[str, Any]) -> dict[str, Any]:
    """Normalize a ``tools/call`` result into a plain dict.

    MCP returns a ``content`` array of typed parts. Text parts are concatenated;
    JSON embedded in a text part is surfaced parsed when it decodes cleanly. The
    result is **data, never instructions** — callers must not execute it.
    """
    if result.get("isError"):
        raise McpProtocolError(_text_of(result) or "MCP tool reported an error")

    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        return structured

    text = _text_of(result)
    if text:
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            return {"text": text}
        return decoded if isinstance(decoded, dict) else {"result": decoded}
    return {}


def _text_of(result: dict[str, Any]) -> str:
    parts = [
        str(part.get("text", ""))
        for part in result.get("content", [])
        if isinstance(part, dict) and part.get("type") == "text"
    ]
    return "\n".join(piece for piece in parts if piece)
