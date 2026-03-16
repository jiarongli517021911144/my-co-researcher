from __future__ import annotations

import asyncio
import re
from collections import defaultdict, deque
from typing import TYPE_CHECKING, Any

from loguru import logger

from coresearcher.bus.events import OutboundMessage
from coresearcher.bus.queue import MessageBus
from coresearcher.channels.base import BaseChannel
from coresearcher.config.schema import QQConfig

try:
    import botpy  # type: ignore
    from botpy.message import C2CMessage, DirectMessage, GroupMessage

    QQ_AVAILABLE = True
except Exception:  # pragma: no cover
    botpy = None
    C2CMessage = None
    DirectMessage = None
    GroupMessage = None
    QQ_AVAILABLE = False

if TYPE_CHECKING:
    from botpy.message import C2CMessage, DirectMessage, GroupMessage

_MENTION_RE = re.compile(r"<@!\d+>")


def _make_bot_class(channel: "QQChannel") -> "type[botpy.Client]":
    intents = botpy.Intents(public_messages=True, direct_message=True)

    class _Bot(botpy.Client):
        def __init__(self):
            super().__init__(intents=intents, is_sandbox=channel.config.sandbox)

        async def on_ready(self):
            robot = getattr(self, "robot", None)
            logger.info("QQ bot ready: {}", getattr(robot, "name", "unknown"))

        async def on_c2c_message_create(self, message: "C2CMessage"):
            await channel._on_c2c_message(message)

        async def on_group_at_message_create(self, message: "GroupMessage"):
            await channel._on_group_message(message)

        async def on_direct_message_create(self, message: "DirectMessage"):
            await channel._on_direct_message(message)

        async def on_error(self, event_method: str, *args: Any, **kwargs: Any) -> None:
            logger.exception("QQ bot error on {}", event_method)

    return _Bot


class QQChannel(BaseChannel):
    name = "qq"

    def __init__(self, config: QQConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config: QQConfig = config
        self._client: "botpy.Client | None" = None
        self._bot_task: asyncio.Task[None] | None = None
        self._processed_ids: deque[str] = deque(maxlen=1000)
        self._msg_seq: defaultdict[str, int] = defaultdict(int)

    async def start(self) -> None:
        if not QQ_AVAILABLE:
            logger.warning("QQ SDK not installed; channel stays disabled")
            return
        if not self.config.app_id or not self.config.secret:
            logger.warning("QQ app_id/secret not configured")
            return

        self._running = True
        bot_class = _make_bot_class(self)
        self._client = bot_class()
        self._bot_task = asyncio.create_task(self._run_bot(), name="coresearcher-qq-bot")
        logger.info("QQ channel starting")

    async def _run_bot(self) -> None:
        assert self._client is not None
        while self._running:
            try:
                await self._client.start(appid=str(self.config.app_id), secret=self.config.secret)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover
                logger.warning("QQ bot connection error: {}", exc)
            if self._running:
                logger.info("Reconnecting QQ bot in 5 seconds...")
                await asyncio.sleep(5)

    async def stop(self) -> None:
        self._running = False
        if self._client is not None:
            try:
                await self._client.close()
            except Exception as exc:  # pragma: no cover
                logger.debug("Error closing QQ client: {}", exc)
        if self._bot_task is not None:
            self._bot_task.cancel()
            try:
                await self._bot_task
            except asyncio.CancelledError:
                pass
            self._bot_task = None
        self._client = None
        logger.info("QQ channel stopped")

    async def send(self, msg: OutboundMessage) -> None:
        if not self._client:
            logger.warning("QQ client not initialized")
            return

        metadata = msg.metadata or {}
        qq_type = metadata.get("qq_type", "c2c")
        reply_id = msg.reply_to or metadata.get("message_id")
        try:
            if qq_type == "group":
                await self._client.api.post_group_message(
                    group_openid=msg.chat_id,
                    msg_type=0,
                    content=msg.content,
                    msg_id=reply_id,
                    msg_seq=self._next_seq(msg.chat_id),
                    event_id=metadata.get("event_id"),
                )
                return
            if qq_type == "direct":
                guild_id = metadata.get("guild_id") or msg.chat_id
                await self._client.api.post_dms(
                    guild_id=guild_id,
                    content=msg.content,
                    msg_id=reply_id,
                    event_id=metadata.get("event_id"),
                )
                return

            await self._client.api.post_c2c_message(
                openid=msg.chat_id,
                msg_type=0,
                content=msg.content,
                msg_id=reply_id,
                msg_seq=self._next_seq(msg.chat_id),
                event_id=metadata.get("event_id"),
            )
        except Exception as exc:  # pragma: no cover
            logger.error("Error sending QQ message: {}", exc)

    async def _on_c2c_message(self, message: "C2CMessage") -> None:
        if self._is_duplicate(message.id):
            return
        sender_id = str(getattr(message.author, "user_openid", "") or "unknown")
        content = (message.content or "").strip()
        if not content:
            return
        await self._handle_message(
            sender_id=sender_id,
            chat_id=sender_id,
            content=content,
            metadata={
                "message_id": message.id,
                "event_id": message.event_id,
                "qq_type": "c2c",
            },
        )

    async def _on_group_message(self, message: "GroupMessage") -> None:
        if self._is_duplicate(message.id):
            return
        sender_id = str(getattr(message.author, "member_openid", "") or "unknown")
        chat_id = str(message.group_openid or "")
        content = self._normalize_group_content(message.content or "")
        if not content or not chat_id:
            return
        await self._handle_message(
            sender_id=sender_id,
            chat_id=chat_id,
            content=content,
            metadata={
                "message_id": message.id,
                "event_id": message.event_id,
                "qq_type": "group",
                "group_openid": chat_id,
            },
        )

    async def _on_direct_message(self, message: "DirectMessage") -> None:
        if self._is_duplicate(message.id):
            return
        sender_id = str(getattr(message.author, "id", "") or "unknown")
        content = (message.content or "").strip()
        if not content or not message.guild_id:
            return
        await self._handle_message(
            sender_id=sender_id,
            chat_id=str(message.guild_id),
            content=content,
            metadata={
                "message_id": message.id,
                "event_id": message.event_id,
                "qq_type": "direct",
                "guild_id": message.guild_id,
                "channel_id": message.channel_id,
            },
        )

    def _next_seq(self, chat_id: str) -> int:
        self._msg_seq[chat_id] += 1
        return self._msg_seq[chat_id]

    def _is_duplicate(self, message_id: str | None) -> bool:
        if not message_id:
            return False
        if message_id in self._processed_ids:
            return True
        self._processed_ids.append(message_id)
        return False

    def _normalize_group_content(self, content: str) -> str:
        return _MENTION_RE.sub("", content).strip()
