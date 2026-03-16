# Providers

This package is the public provider abstraction used by the runtime.

## Main Files

- `base.py`
  Shared provider types
- `factory.py`
  Provider factory from config
- `mock_provider.py`
  Offline provider for demos
- `litellm_provider.py`
  Main adapter for hosted model providers
- `custom_provider.py`
  Generic OpenAI-compatible endpoint support
- `openai_codex_provider.py`
  Codex-specific adapter
- `registry.py`
  Re-exported provider registry helpers

## Quick Checks

```bash
python demos/providers_demo.py
python demos/open_source_demo.py
```
