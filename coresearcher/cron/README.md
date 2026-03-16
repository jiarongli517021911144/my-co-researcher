# Cron

This package stores and runs scheduled jobs.

## Main Files

- `types.py`
  Cron job model
- `store.py`
  JSON-backed persistence
- `service.py`
  Polling and execution loop

## Quick Checks

```bash
python demos/cron_demo.py
python -m coresearcher cron list
```
