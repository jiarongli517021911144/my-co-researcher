from __future__ import annotations

from loguru import logger

from coresearcher.bus.events import OutboundMessage
from coresearcher.bus.queue import MessageBus
from coresearcher.channels.base import BaseChannel
from coresearcher.config.schema import FeishuConfig

try:
    import lark_oapi as lark  # type: ignore

    FEISHU_AVAILABLE = True
except Exception:  # pragma: no cover
    lark = None
    FEISHU_AVAILABLE = False


class FeishuChannel(BaseChannel):
    name = "feishu"

    def __init__(self, config: FeishuConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config: FeishuConfig = config
        self._client = None

    async def start(self) -> None:
        if not FEISHU_AVAILABLE:
            logger.warning("Feishu SDK not installed; channel stays disabled")
            return
        if not self.config.app_id or not self.config.app_secret:
            logger.warning("Feishu app_id/app_secret not configured")
            return
        self._running = True
        self._client = lark.Client.builder().app_id(self.config.app_id).app_secret(self.config.app_secret).build()
        logger.info("Feishu channel started")

    async def stop(self) -> None:
        self._running = False
        self._client = None
        logger.info("Feishu channel stopped")

    async def send(self, msg: OutboundMessage) -> None:
        if not self._running:
            logger.warning("Feishu channel is not running; dropping outbound message")
            return
        logger.info("[Feishu -> {}] {}", msg.chat_id, msg.content)
