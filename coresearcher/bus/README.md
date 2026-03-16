# Message Bus

This package defines the async bus used by channels, cron, and the agent.

## Main Files

- `events.py`
  Inbound and outbound message types
- `queue.py`
  Async queue wrapper used by the runtime

## Quick Check

```bash
python demos/bus_demo.py
```
