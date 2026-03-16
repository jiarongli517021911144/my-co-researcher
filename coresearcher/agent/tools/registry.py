from __future__ import annotations

from typing import TYPE_CHECKING, Any

from coresearcher.agent.subagent.manager import SubagentManager
from coresearcher.agent.tools.base import Tool
from coresearcher.agent.tools.cron import CronTool
from coresearcher.agent.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from coresearcher.agent.tools.mcp import MCPTool
from coresearcher.agent.tools.memory_search import MemorySearchTool
from coresearcher.agent.tools.message import MessageTool
from coresearcher.agent.tools.shell import ExecTool
from coresearcher.agent.tools.spawn import SpawnTool
from coresearcher.agent.tools.web import WebFetchTool, WebSearchTool
from coresearcher.bus.queue import MessageBus
from coresearcher.config.schema import Config
from coresearcher.cron import CronStore

if TYPE_CHECKING:
    from coresearcher.cron.service import CronService


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get_definitions(self) -> list[dict[str, Any]]:
        return [tool.definition() for tool in self._tools.values()]

    async def execute(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"Unknown tool: {name}")
        return await tool.execute(arguments or {})

    def names(self) -> list[str]:
        return sorted(self._tools)


def build_default_registry(
    config: Config,
    *,
    bus: MessageBus | None = None,
    subagents: SubagentManager | None = None,
    memory_search: callable | None = None,
    cron_store: CronStore | None = None,
    cron_service: CronService | None = None,
) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(ReadFileTool(config.tools.allowed_dir, config.tools.restrict_to_workspace))
    registry.register(WriteFileTool(config.tools.allowed_dir, config.tools.restrict_to_workspace))
    registry.register(EditFileTool(config.tools.allowed_dir, config.tools.restrict_to_workspace))
    registry.register(ListDirTool(config.tools.allowed_dir, config.tools.restrict_to_workspace))
    registry.register(ExecTool(timeout_seconds=config.tools.shell_timeout_seconds))
    registry.register(WebSearchTool(config.tools.web_search_api_key, config.tools.web_search_base_url, config.tools.max_web_results))
    registry.register(WebFetchTool())
    registry.register(MCPTool(config.tools.mcp_servers))
    if bus is not None:
        registry.register(MessageTool(bus))
    if subagents is not None:
        registry.register(SpawnTool(subagents))
    if memory_search is not None:
        registry.register(MemorySearchTool(memory_search))
    if cron_store is not None:
        registry.register(CronTool(cron_store, cron_service))
    return registry
