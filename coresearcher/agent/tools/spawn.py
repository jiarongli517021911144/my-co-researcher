
from __future__ import annotations

import asyncio
from typing import Any

from coresearcher.agent.subagent.manager import SubagentManager
from coresearcher.agent.tools.base import Tool


class SpawnTool(Tool):
    name = "spawn"
    description = "Spawn a background async task that sleeps for a given delay"
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "delay": {"type": "number", "minimum": 0},
        },
        "required": [],
    }

    def __init__(self, manager: SubagentManager) -> None:
        self.manager = manager

    async def execute(self, arguments: dict[str, Any]) -> str:
        delay = float(arguments.get("delay") or 0)
        name = arguments.get("name")

        async def _runner() -> None:
            await asyncio.sleep(delay)

        task_id = self.manager.spawn(_runner, name=name)
        return task_id
