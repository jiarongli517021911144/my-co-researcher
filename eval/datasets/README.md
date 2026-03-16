# Evaluation Datasets

This directory stores the public task definitions used by the evaluation engine.

## Included Datasets

- `deep_research.json`
- `dynamic_interaction.json`
- `safety_risk_control.json`

## Task Shape

Each task includes:

- `task_id`
- `title`
- `category`
- `prompt`
- `ground_truth`
- `eval_dimensions`
- `standard_trace`

Optional fields:

- `mock_output`
- `mock_trace`

`standard_trace` is used for live trace comparison. `mock_output` and `mock_trace` are used for replay evaluation and offline debugging.

## Quick Checks

```bash
python demos/eval_demo.py
python demos/eval_live_demo.py
```
