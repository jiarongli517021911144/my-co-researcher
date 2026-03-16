from __future__ import annotations

from coresearcher.bus.queue import MessageBus
from coresearcher.channels.console import ConsoleChannel
from coresearcher.channels.feishu import FeishuChannel
from coresearcher.channels.qq import QQChannel
from coresearcher.config.schema import Config


def build_channels(config: Config, bus: MessageBus, include_console: bool = True) -> list:
    channels = []
    if include_console and config.channels.cli.enabled:
        channels.append(ConsoleChannel(config.channels.cli, bus))
    if config.channels.feishu.enabled:
        channels.append(FeishuChannel(config.channels.feishu, bus))
    if config.channels.qq.enabled:
        channels.append(QQChannel(config.channels.qq, bus))
    return channels
