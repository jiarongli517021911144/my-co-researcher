from __future__ import annotations

from typing import Any

from coresearcher.agent.tools.base import Tool
from coresearcher.config.schema import MCPServerConfig


class MCPTool(Tool):
    name = "mcp"
    description = "Inspect configured MCP servers"
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["list", "describe"]},
            "name": {"type": "string"},
        },
        "required": ["action"],
    }

    def __init__(self, servers: dict[str, MCPServerConfig]) -> None:
        self.servers = servers

    async def execute(self, arguments: dict[str, Any]) -> Any:
        action = arguments["action"]
        if action == "list":
            return sorted(self.servers)
        if action == "describe":
            name = arguments["name"]
            server = self.servers.get(name)
            if server is None:
                raise KeyError(f"Unknown MCP server: {name}")
            return server.model_dump(mode="json")
        raise ValueError(f"Unsupported action: {action}")
