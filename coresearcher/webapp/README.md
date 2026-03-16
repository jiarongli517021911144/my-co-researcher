# Web App

This package serves the local multi-page web UI.

## Pages

- `/`
  Overview dashboard
- `/chat`
  Chat and live trace stream
- `/workspace`
  Workspace file browser and editor
- `/sessions`
  Session history browser
- `/memory`
  Memory search and recent entries
- `/config`
  Config and cron inspection

## Main Files

- `server.py`
- `static/index.html`
- `static/chat.html`
- `static/workspace.html`
- `static/sessions.html`
- `static/memory.html`
- `static/config.html`

## Quick Check

```bash
python -m coresearcher web
```

Then open `http://127.0.0.1:8765`.
