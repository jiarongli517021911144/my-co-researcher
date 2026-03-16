# Provider Compatibility Layer

This directory keeps the lower-level provider implementations that the public
`coresearcher.providers` package reuses.

## Why It Exists

- Preserve compatibility with the earlier provider layout
- Keep the public package thinner while reusing stable provider logic
- Allow gradual migration without breaking the runtime

## Quick Check

```bash
python demos/providers_demo.py
```
