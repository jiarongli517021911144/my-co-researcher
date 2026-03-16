from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from loguru import logger

from coresearcher.bus.events import InboundMessage, OutboundMessage
from coresearcher.bus.queue import MessageBus


class BaseChannel(ABC):
    name: str = "base"

    def __init__(self, config: Any, bus: MessageBus):
        self.config = config
        self.bus = bus
        self._running = False

    @abstractmethod
    async def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def stop(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def send(self, msg: OutboundMessage) -> None:
        raise NotImplementedError

    def is_allowed(self, sender_id: str) -> bool:
        allow_list = getattr(self.config, "allow_from", [])
        if not allow_list:
            return True
        sender_str = str(sender_id)
        return sender_str in allow_list or any(part in allow_list for part in sender_str.split("|"))

    async def _handle_message(
        self,
        sender_id: str,
        chat_id: str,
        content: str,
        media: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not self.is_allowed(sender_id):
            logger.warning("Access denied for sender {} on channel {}", sender_id, self.name)
            return
        await self.bus.publish_inbound(
            InboundMessage(
                channel=self.name,
                sender_id=str(sender_id),
                chat_id=str(chat_id),
                content=content,
                media=media or [],
                metadata=metadata or {},
            )
        )

    @property
    def is_running(self) -> bool:
        return self._running
