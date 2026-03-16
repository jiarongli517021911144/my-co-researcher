# Evaluation Engine

This package provides replay and live evaluation helpers for `coresearcher`.

## Main Files

- `types.py`
  Task, run result, and report models
- `runner.py`
  Dataset loading, batch execution, aggregation, and Markdown report generation
- `judge.py`
  LLM-as-a-judge plus heuristic fallback scoring
- `live_runner.py`
  Live agent execution against the same task format

## Quick Checks

```bash
python demos/eval_demo.py
python demos/eval_live_demo.py
```
