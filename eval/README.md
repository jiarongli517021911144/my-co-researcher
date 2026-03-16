# Evaluation Assets

This directory contains public evaluation inputs and local report outputs.

## Public Inputs

- `datasets/`
  Static task definitions used by replay and live evaluation flows

## Generated Outputs

- `reports/`
  Markdown reports written by demo or evaluation runs

Generated reports are ignored for the public repo and should be treated as local artifacts.

## Quick Checks

```bash
python demos/eval_demo.py
python demos/eval_live_demo.py
```
