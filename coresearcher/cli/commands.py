from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer

from coresearcher import __version__
from coresearcher.config.loader import default_config_path, load_config, save_config
from coresearcher.cron import CronJob, CronStore
from coresearcher.providers.registry import find_by_name
from coresearcher.webapp.server import run_server

app = typer.Typer(help="coresearcher personal AI assistant framework", no_args_is_help=True)
cron_app = typer.Typer(help="Manage persisted cron jobs", no_args_is_help=True)
app.add_typer(cron_app, name="cron")


async def _run_once(message: str, provider: str | None = None, model: str | None = None) -> str:
    from coresearcher.bus import InboundMessage
    from coresearcher.runtime import build_runtime

    config = load_config()
    runtime = build_runtime(config, provider_name=provider, model=model)
    outbound = await runtime.agent._process_message(
        InboundMessage(channel="cli", sender_id="cli-user", chat_id="cli", content=message)
    )
    return outbound.content


@app.command(help="Bootstrap a workspace and write a starter config file.")
def onboard(
    path: str | None = typer.Option(None, help="Workspace path"),
    provider: str | None = typer.Option(None, help="Default provider"),
    model: str | None = typer.Option(None, help="Default model"),
) -> None:
    from coresearcher.workspace.bootstrap import bootstrap_workspace

    config = load_config()
    workspace_default = path or config.workspace.path
    workspace_path = Path(
        typer.prompt("Workspace path", default=str(Path(workspace_default).expanduser()))
    ).expanduser()
    created = bootstrap_workspace(workspace_path)
    config.workspace.path = str(created)
    if config.tools.restrict_to_workspace:
        config.tools.allowed_dir = str(created)

    provider_name = (provider or typer.prompt("Default provider", default=config.providers.default)).replace("-", "_")
    config.providers.default = provider_name

    default_model = model or typer.prompt(
        "Default model",
        default=config.providers.resolve(provider_name)[1].model or config.providers.default_model,
    )
    config.providers.default_model = default_model
    resolved_name, resolved_provider = config.providers.resolve(provider_name)
    provider_updates = {"model": default_model, "enabled": True}

    spec = find_by_name(provider_name)
    if spec and spec.env_key:
        api_key = typer.prompt(
            f"{provider_name} API key (blank to keep current)",
            default=resolved_provider.api_key or "",
            hide_input=True,
        )
        if api_key:
            provider_updates["api_key"] = api_key
    if spec and spec.default_api_base:
        provider_updates["api_base"] = resolved_provider.api_base or spec.default_api_base

    setattr(config.providers, resolved_name, resolved_provider.model_copy(update=provider_updates))
    save_path = save_config(config)
    typer.echo(f"Workspace ready: {created}")
    typer.echo(f"Config saved: {save_path}")


@app.command("agent", help="Run one chat turn or start an interactive CLI session.")
def agent_command(
    message: str | None = typer.Option(None, "-m", "--message", help="Single-message mode"),
    provider: str | None = typer.Option(None, help="Override provider"),
    model: str | None = typer.Option(None, help="Override model"),
) -> None:
    if message is not None:
        typer.echo(asyncio.run(_run_once(message, provider=provider, model=model)))
        return

    typer.echo("coresearcher CLI mode. Type 'exit' or 'quit' to stop.")
    while True:
        try:
            prompt = typer.prompt("you")
        except (EOFError, KeyboardInterrupt):
            typer.echo("")
            break
        if prompt.strip().lower() in {"exit", "quit"}:
            break
        typer.echo(asyncio.run(_run_once(prompt, provider=provider, model=model)))


@app.command(help="Run the gateway that wires the agent, channels, cron jobs, and heartbeats.")
def gateway(
    provider: str | None = typer.Argument(None),
    model: str | None = typer.Option(None, help="Override model"),
    dry_run: bool = typer.Option(False, help="Show resolved runtime only"),
    interval_seconds: int = typer.Option(30, help="Cron polling interval"),
    run_seconds: int | None = typer.Option(None, help="Run for N seconds then stop"),
) -> None:
    from coresearcher.runtime import build_runtime, serve_gateway

    config = load_config()
    resolved_name, resolved = config.providers.resolve(provider)
    if model:
        resolved = resolved.model_copy(update={"model": model})
    payload = {
        "provider": resolved_name,
        "model": resolved.model or config.providers.default_model,
        "channels": config.channels.enabled_names(),
        "cron_jobs": [job.name for job in CronStore(config.cron.store_path).load()] + ["__heartbeat__"],
        "workspace": config.workspace.path,
    }
    if dry_run:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    runtime = build_runtime(config, provider_name=provider, model=model)
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))

    async def _main() -> None:
        if run_seconds is None:
            await serve_gateway(runtime, interval_seconds=interval_seconds)
            return
        task = asyncio.create_task(serve_gateway(runtime, interval_seconds=interval_seconds))
        try:
            await asyncio.sleep(run_seconds)
        finally:
            runtime.cron_service.stop()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        typer.echo("Gateway stopped")


@cron_app.command("add")
def cron_add(
    name: str = typer.Option(..., help="Job name"),
    message: str = typer.Option(..., help="Message content"),
    cron: str = typer.Option(..., help="Cron expression"),
    channel: str = typer.Option("cli", help="Target channel"),
    chat_id: str = typer.Option("cron", help="Target chat id"),
) -> None:
    config = load_config()
    store = CronStore(config.cron.store_path)
    job = CronJob(name=name, schedule=cron, payload={"message": message, "channel": channel, "chat_id": chat_id})
    store.add(job)
    typer.echo(f"Added cron job: {name}")


@cron_app.command("list")
def cron_list() -> None:
    config = load_config()
    store = CronStore(config.cron.store_path)
    jobs = store.load()
    if not jobs:
        typer.echo("No cron jobs")
        return
    for job in jobs:
        typer.echo(f"- {job.name}: {job.schedule} -> {job.payload.get('channel', 'cli')}:{job.payload.get('chat_id', job.name)}")


@cron_app.command("remove")
def cron_remove(name: str) -> None:
    config = load_config()
    store = CronStore(config.cron.store_path)
    removed = store.remove(name)
    if not removed:
        raise typer.Exit(code=1)
    typer.echo(f"Removed cron job: {name}")


@app.command(help="Start the local multi-page web UI.")
def web(
    host: str = typer.Option("127.0.0.1", help="Bind host"),
    port: int = typer.Option(8765, help="Bind port"),
) -> None:
    run_server(host=host, port=port)


@app.command(help="Print the resolved runtime configuration and enabled features.")
def status() -> None:
    config = load_config()
    store = CronStore(config.cron.store_path)
    provider_name, provider_cfg = config.providers.resolve()
    payload = {
        "version": __version__,
        "config_path": str(default_config_path()),
        "workspace": str(Path(config.workspace.path).expanduser()),
        "provider": provider_name,
        "model": provider_cfg.model or config.providers.default_model,
        "enabled_channels": config.channels.enabled_names(),
        "cron_jobs": [job.name for job in store.load()],
        "mcp_servers": sorted(config.tools.mcp_servers),
    }
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    app()
