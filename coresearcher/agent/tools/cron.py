
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from coresearcher.agent.tools.base import Tool
from coresearcher.cron import CronJob, CronStore

if TYPE_CHECKING:
    from coresearcher.cron.service import CronService


class CronTool(Tool):
    name = "cron"
    description = "Manage persisted cron jobs"
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["list", "add", "remove"]},
            "name": {"type": "string"},
            "schedule": {"type": "string"},
            "message": {"type": "string"},
            "channel": {"type": "string"},
            "chat_id": {"type": "string"},
        },
        "required": ["action"],
    }

    def __init__(self, store: CronStore, service: CronService | None = None) -> None:
        self.store = store
        self.service = service

    async def execute(self, arguments: dict[str, Any]) -> Any:
        action = arguments["action"]
        if action == "list":
            return [
                {"name": job.name, "schedule": job.schedule, "payload": job.payload}
                for job in self.store.load()
            ]
        if action == "remove":
            name = arguments["name"]
            removed_from_store = self.store.remove(name)
            removed_from_service = False
            if self.service is not None:
                removed_from_service = self.service.remove_job(name)
            return {
                "removed": removed_from_store or removed_from_service,
                "name": name,
            }
        if action == "add":
            job = CronJob(
                name=arguments["name"],
                schedule=arguments["schedule"],
                payload={
                    "message": arguments.get("message", ""),
                    "channel": arguments.get("channel", "cli"),
                    "chat_id": arguments.get("chat_id", arguments.get("channel", "cron")),
                },
            )
            self.store.add(job)
            if self.service is not None:
                self.service.add_job(job)
            return {"added": job.name, "schedule": job.schedule}
        raise ValueError(f"Unsupported action: {action}")
