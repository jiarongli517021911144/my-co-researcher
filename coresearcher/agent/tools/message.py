
from __future__ import annotations

from typing import Any

from coresearcher.agent.tools.base import Tool
from coresearcher.bus.events import OutboundMessage
from coresearcher.bus.queue import MessageBus


class MessageTool(Tool):
    name = "message"
    description = "Send a message to a channel via the outbound bus"
    parameters = {
        "type": "object",
        "properties": {
            "channel": {"type": "string"},
            "chat_id": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["channel", "chat_id", "content"],
    }

    def __init__(self, bus: MessageBus) -> None:
        self.bus = bus

    async def execute(self, arguments: dict[str, Any]) -> str:
        await self.bus.publish_outbound(
            OutboundMessage(
                channel=arguments["channel"],
                chat_id=arguments["chat_id"],
                content=arguments["content"],
            )
        )
        return "queued"
