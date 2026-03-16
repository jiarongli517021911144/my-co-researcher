# coresearcher package

This is the public Python package that wires the runtime together.

## Main Entry Points

- `__main__.py`
  `python -m coresearcher`
- `runtime.py`
  Runtime assembly for the provider, agent, channels, cron, heartbeat, memory, and sessions.
- `cli/`
  Typer-based command-line interface.
- `agent/`
  Core reasoning and tool execution pipeline.
- `providers/`
  Provider abstraction and factory.
- `channels/`
  CLI, Feishu, and QQ adapters.

## Quick Checks

```bash
python -m coresearcher --help
python -m coresearcher status
python -m coresearcher gateway --dry-run
```
