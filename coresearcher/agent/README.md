# Agent Core

This package contains the main agent runtime.

## Responsibilities

- Build context from workspace files, memory, history, and skills
- Run the provider in a ReAct-style loop
- Execute tools and feed results back into the conversation
- Persist sessions and flush older history into memory
- Optionally use planning, reflexion, subagents, and RAG

## Key Modules

- `loop.py`
- `context/`
- `memory/`
- `planning/`
- `reflexion/`
- `rag/`
- `skills/`
- `subagent/`
- `tools/`

## Quick Checks

```bash
python -m coresearcher agent -m "hello"
python demos/open_source_demo.py
python demos/tools_demo.py
```
