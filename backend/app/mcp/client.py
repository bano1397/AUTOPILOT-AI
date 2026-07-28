"""MCP client transports: stdio (subprocess) and HTTP.

Both implement the same tiny surface — ``list_tools`` and ``call_tool`` — so the
adapter and registry are transport-agnostic.

Security posture: servers are only ever reached from the explicit allow-list in
configuration (``MCP_SERVERS``); nothing here discovers or trusts a server named
by remote content, and returned content is treated as untrusted data.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Protocol

import httpx

from app.core.logging import get_logger
from app.mcp.protocol import (
    PROTOCOL_VERSION,
    McpProtocolError,
    McpToolDescriptor,
    parse_call_result,
    parse_tools,
    request,
    result_of,
)

logger = get_logger("app.mcp.client")

_TIMEOUT = 30.0
_CLIENT_INFO = {"name": "autopilot-ai", "version": "1.0.0"}


class MCPClient(Protocol):
    """Transport-agnostic MCP client contract."""

    name: str

    async def list_tools(self) -> list[McpToolDescriptor]:
        """Return the tools the server advertises."""
        ...

    async def call_tool(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Invoke a remote tool and return its normalized result."""
        ...


class HttpMCPClient:
    """MCP over HTTP: one JSON-RPC POST per call."""

    def __init__(
        self,
        name: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.name = name
        self._url = url
        self._headers = headers or {}
        self._client = client

    async def _rpc(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = request(method, params)
        try:
            if self._client is not None:
                response = await self._client.post(
                    self._url, json=payload, headers=self._headers
                )
            else:
                async with httpx.AsyncClient(timeout=_TIMEOUT) as owned:
                    response = await owned.post(
                        self._url, json=payload, headers=self._headers
                    )
        except httpx.HTTPError as exc:
            raise McpProtocolError(f"MCP server '{self.name}' unreachable: {exc}") from exc
        if response.status_code >= 400:
            raise McpProtocolError(
                f"MCP server '{self.name}' returned HTTP {response.status_code}"
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise McpProtocolError(
                f"MCP server '{self.name}' returned non-JSON body"
            ) from exc
        return result_of(body if isinstance(body, dict) else {})

    async def list_tools(self) -> list[McpToolDescriptor]:
        await self._rpc(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": _CLIENT_INFO,
            },
        )
        return parse_tools(await self._rpc("tools/list"))

    async def call_tool(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = await self._rpc("tools/call", {"name": tool, "arguments": arguments})
        return parse_call_result(result)


class StdioMCPClient:
    """MCP over stdio: newline-delimited JSON-RPC to a child process.

    A process is spawned per batch of calls and shut down afterwards. Long-lived
    sessions would be more efficient but need supervision and restart policy;
    that is deliberately out of scope until a real workload asks for it.
    """

    def __init__(self, name: str, command: str, args: list[str] | None = None) -> None:
        self.name = name
        self._command = command
        self._args = args or []

    async def _session(self, calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
        try:
            process = await asyncio.create_subprocess_exec(
                self._command,
                *self._args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (OSError, ValueError) as exc:
            raise McpProtocolError(
                f"MCP server '{self.name}' failed to start: {exc}"
            ) from exc

        payload = "".join(json.dumps(call) + "\n" for call in calls).encode()
        try:
            stdout, _stderr = await asyncio.wait_for(
                process.communicate(payload), timeout=_TIMEOUT
            )
        except TimeoutError as exc:
            process.kill()
            raise McpProtocolError(f"MCP server '{self.name}' timed out") from exc

        responses: list[dict[str, Any]] = []
        for line in stdout.decode(errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                decoded = json.loads(line)
            except json.JSONDecodeError:
                continue  # servers may log to stdout; ignore non-JSON lines
            if isinstance(decoded, dict) and "id" in decoded:
                responses.append(decoded)
        if not responses:
            raise McpProtocolError(f"MCP server '{self.name}' returned no responses")
        return responses

    async def list_tools(self) -> list[McpToolDescriptor]:
        responses = await self._session(
            [
                request(
                    "initialize",
                    {
                        "protocolVersion": PROTOCOL_VERSION,
                        "capabilities": {},
                        "clientInfo": _CLIENT_INFO,
                    },
                    id=1,
                ),
                request("tools/list", id=2),
            ]
        )
        return parse_tools(result_of(responses[-1]))

    async def call_tool(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        responses = await self._session(
            [
                request(
                    "initialize",
                    {
                        "protocolVersion": PROTOCOL_VERSION,
                        "capabilities": {},
                        "clientInfo": _CLIENT_INFO,
                    },
                    id=1,
                ),
                request("tools/call", {"name": tool, "arguments": arguments}, id=2),
            ]
        )
        return parse_call_result(result_of(responses[-1]))
