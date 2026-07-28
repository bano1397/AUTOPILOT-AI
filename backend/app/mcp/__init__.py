"""Model Context Protocol layer.

Two directions:

* **Consume** — connect to configured MCP servers, adapt their tools into the
  native tool registry (``client``, ``adapter``, ``registry``).
* **Expose** — serve AutoPilot's own tools to external MCP clients (``server``).
"""

from app.mcp.client import HttpMCPClient, MCPClient, StdioMCPClient
from app.mcp.protocol import McpProtocolError, McpToolDescriptor
from app.mcp.registry import (
    McpServerDefinition,
    discover_mcp_tools,
    parse_server_definitions,
    register_server_tools,
)

__all__ = [
    "HttpMCPClient",
    "MCPClient",
    "McpProtocolError",
    "McpServerDefinition",
    "McpToolDescriptor",
    "StdioMCPClient",
    "discover_mcp_tools",
    "parse_server_definitions",
    "register_server_tools",
]
