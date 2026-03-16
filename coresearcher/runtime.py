from __future__ import annotations

import asyncio
from dataclasses import dataclass

from loguru import logger

from coresearcher.agent import AgentLoop
from coresearcher.agent.memory import MemoryStore
from coresearcher.agent.subagent import SubagentManager
from coresearcher.agent.tools import build_default_registry
from coresearcher.bus import MessageBus
from coresearcher.channels.factory import build_channels
from coresearcher.channels.manager import ChannelManager
from coresearcher.config import Config
from coresearcher.cron import CronJob, CronService, CronStore
from coresearcher.heartbeat import HeartbeatService
from coresearcher.providers.factory import create_provider
from coresearcher.session import SessionManager


@dataclass
class Runtime:
    config: Config
    bus: MessageBus
    agent: AgentLoop
    channels: ChannelManager
    provider: object
    cron_service: CronService
    cron_store: CronStore
    heartbeat: HeartbeatService


async def _handle_cron_job(bus: MessageBus, job: CronJob) -> None:
    payload = job.payload
    from coresearcher.bus.events import InboundMessage

    await bus.publish_inbound(
        InboundMessage(
            channel=payload.get("channel", "cli"),
            sender_id="cron",
            chat_id=payload.get("chat_id", job.name),
            content=payload.get("message", ""),
            metadata={"cron_job": job.name},
        )
    )


async def _handle_heartbeat(bus: MessageBus, heartbeat: HeartbeatService) -> None:
    msg = heartbeat.build_inbound_message()
    if msg is not None:
        await bus.publish_inbound(msg)


def build_runtime(config: Config, provider_name: str | None = None, model: str | None = None) -> Runtime:
    if model:
        resolved_name, resolved = config.providers.resolve(provider_name)
        setattr(config.providers, resolved_name, resolved.model_copy(update={"model": model}))
        config.providers.default = resolved_name
    provider = create_provider(config, provider_name)
    bus = MessageBus()
    cron_store = CronStore(config.cron.store_path)
    heartbeat = HeartbeatService(config.workspace.path)
    memory_store = MemoryStore(config.memory.directory)
    session_manager = SessionManager(config.memory.session_dir)
    subagents = SubagentManager()

    async def cron_handler(job: CronJob) -> None:
        await _handle_cron_job(bus, job)

    cron_service = CronService(cron_handler)
    for job in cron_store.load():
        cron_service.add_job(job)
    heartbeat_schedule = f"*/{max(1, config.cron.heartbeat_minutes)} * * * *"
    cron_service.add_job(CronJob(name="__heartbeat__", schedule=heartbeat_schedule, payload={"kind": "heartbeat"}))

    original_handler = cron_service.handler

    async def multiplex(job: CronJob) -> None:
        if job.name == "__heartbeat__":
            await _handle_heartbeat(bus, heartbeat)
            return
        await original_handler(job)

    cron_service.handler = multiplex

    registry = build_default_registry(
        config,
        bus=bus,
        subagents=subagents,
        memory_search=memory_store.search,
        cron_store=cron_store,
        cron_service=cron_service,
    )
    agent = AgentLoop(
        config,
        bus,
        provider,
        session_manager=session_manager,
        memory_store=memory_store,
        tool_registry=registry,
        subagents=subagents,
    )
    channels = ChannelManager(bus, build_channels(config, bus, include_console=True))

    return Runtime(config, bus, agent, channels, provider, cron_service, cron_store, heartbeat)


async def serve_gateway(runtime: Runtime, interval_seconds: int = 30) -> None:
    await runtime.channels.start()
    agent_task = asyncio.create_task(runtime.agent.run(), name="coresearcher-agent-loop")
    cron_task = asyncio.create_task(runtime.cron_service.serve(interval_seconds=interval_seconds), name="coresearcher-cron-loop")
    try:
        await asyncio.gather(agent_task, cron_task)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Gateway runtime crashed")
    finally:
        runtime.cron_service.stop()
        agent_task.cancel()
        cron_task.cancel()
        for task in (agent_task, cron_task):
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        await runtime.channels.stop()
