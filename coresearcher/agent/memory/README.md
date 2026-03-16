# Memory

This package handles durable memory for the agent.

## Responsibilities

- Write daily notes under `memory/YYYY-MM-DD.md`
- Maintain long-term memory summaries
- Flush older session history into memory
- Support semantic search over stored notes

## Main Files

- `store.py`
- `daily.py`
- `vector.py`
- `consolidation.py`
- `chroma_sidecar.py`

## Quick Checks

```bash
python demos/memory_demo.py
python demos/chroma_inspect.py stats
python demos/agentic_rag_demo.py
```
