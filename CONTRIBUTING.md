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

## Recommended Smoke Checks

Run these before opening a pull request:

```bash
python -m coresearcher --help
python demos/open_source_demo.py
python demos/workspace_demo.py
python demos/providers_demo.py
python demos/config_demo.py
```

If you touch runtime wiring, also verify the web UI boots:

```bash
CORESEARCHER_CONFIG=$(pwd)/.demo/open_source_demo/config.json python -m coresearcher web
```

## Scope

- Keep public docs focused on the open-source project, not private notes or interview material.
- Do not commit runtime state, logs, local configs, or generated evaluation outputs.
- Prefer demos and smoke checks that run offline with the mock provider when possible.
