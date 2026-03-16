# Channels

This package adapts different message surfaces into the shared bus.

## Included Adapters

- `console.py`
  Local console output for CLI-oriented runs
- `feishu.py`
  Feishu adapter, requires the optional `feishu` extra
- `qq.py`
  QQ adapter, requires the optional `qq` extra
- `manager.py`
  Starts, stops, and fans out outbound messages

## Notes

- The core package works without Feishu or QQ SDKs.
- If an SDK or credential is missing, the related channel stays disabled.
- Channel setup details live in `docs/channels.md`.

## Quick Checks

```bash
python demos/channels_demo.py
python demos/qq_channel_demo.py
python -m coresearcher gateway --dry-run
```
