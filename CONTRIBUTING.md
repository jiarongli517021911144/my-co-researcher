# Contributing

Thanks for contributing to `coresearcher`.

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

If you need Feishu or QQ adapters locally:

```bash
pip install -e ".[feishu,qq]"
```

## Scope

- Keep public docs focused on the open-source project, not private notes or interview material.
- Do not commit runtime state, logs, local configs, or generated evaluation outputs.
- Prefer examples that run offline with the mock provider when possible.
