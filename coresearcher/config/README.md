# Configuration

This package defines the runtime schema and config loading helpers.

## Main Files

- `schema.py`
  Pydantic models for providers, channels, tools, memory, cron, and workspace settings
- `loader.py`
  Load and save helpers for `CORESEARCHER_CONFIG` or the default config path

## Defaults

- Default config path: `~/.coresearcher/config.json`
- Override env var: `CORESEARCHER_CONFIG`

## Quick Check

```bash
python demos/config_demo.py
```
