from __future__ import annotations

import asyncio
from collections.abc import Iterable

from coresearcher.bus.events import OutboundMessage
from coresearcher.bus.queue import MessageBus
from coresearcher.channels.base import BaseChannel


class ChannelManager:
    def __init__(self, bus: MessageBus, channels: Iterable[BaseChannel] | None = None) -> None:
        self.bus = bus
        self.channels: dict[str, BaseChannel] = {channel.name: channel for channel in channels or []}
        self._dispatcher_task: asyncio.Task[None] | None = None

    def register(self, channel: BaseChannel) -> None:
        self.channels[channel.name] = channel

    async def start(self) -> None:
        for channel in self.channels.values():
            await channel.start()
        if self._dispatcher_task is None:
            self._dispatcher_task = asyncio.create_task(self._dispatch_outbound(), name="coresearcher-channel-dispatch")

    async def stop(self) -> None:
        if self._dispatcher_task is not None:
            self._dispatcher_task.cancel()
            try:
                await self._dispatcher_task
            except asyncio.CancelledError:
                pass
            self._dispatcher_task = None
        for channel in self.channels.values():
            await channel.stop()

    async def _dispatch_outbound(self) -> None:
        while True:
            message = await self.bus.consume_outbound()
            await self.send(message)

    async def send(self, msg: OutboundMessage) -> None:
        channel = self.channels.get(msg.channel)
        if channel is None:
            raise KeyError(f"Channel not registered: {msg.channel}")
        await channel.send(msg)
