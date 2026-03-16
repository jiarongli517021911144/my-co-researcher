from __future__ import annotations

from coresearcher.bus.events import OutboundMessage
from coresearcher.bus.queue import MessageBus
from coresearcher.channels.base import BaseChannel
from coresearcher.config.schema import CLIChannelConfig


class ConsoleChannel(BaseChannel):
    name = "cli"

    def __init__(self, config: CLIChannelConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.buffer: list[OutboundMessage] = []

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def send(self, msg: OutboundMessage) -> None:
        self.buffer.append(msg)
        print(msg.content)
