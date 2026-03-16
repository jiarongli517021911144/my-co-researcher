from __future__ import annotations

from typing import Any, Callable

from coresearcher.agent.tools.base import Tool


class MemorySearchTool(Tool):
    name = "memory_search"
    description = "Search the memory store"
    parameters = {
        "type": "object",
        "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1}},
        "required": ["query"],
    }

    def __init__(self, search_fn: Callable[[str, int], Any]) -> None:
                self.search_fn = search_fn

    async def execute(self, arguments: dict[str, Any]) -> Any:
                return self.search_fn(arguments["query"], int(arguments.get("limit") or 5))
