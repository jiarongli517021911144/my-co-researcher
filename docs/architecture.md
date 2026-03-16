# Architecture

`coresearcher` is organized around a small runtime core.

## Runtime Flow

1. A channel produces an inbound message.
2. The message is published to the bus.
3. `AgentLoop` builds context from workspace files, memory, history, and skills.
4. The selected provider returns text or tool calls.
5. Tools execute against the local runtime.
6. The final response is published back to the outbound bus.
7. Channels deliver the response to CLI, web, Feishu, or QQ.

## Main Components

- `coresearcher/runtime.py`
  Composes the provider, bus, channels, cron service, heartbeat service, memory store, and agent loop.
- `coresearcher/agent/`
  Core agent pipeline, including context building, planning, reflexion, RAG, memory, and tool execution.
- `coresearcher/providers/`
  Public provider abstraction and factory. Includes an offline mock provider for demos.
- `coresearcher/channels/`
  Channel adapters for CLI, Feishu, and QQ.
- `coresearcher/webapp/`
  Local Starlette-based web UI.
- `coresearcher/workspace/`
  Workspace bootstrap and packaged context templates.
- `coresearcher/eval/`
  Evaluation engine for replay and live runs.

## Design Notes

- The CLI and web UI are first-class entry points for local development.
- Channel SDKs are optional dependencies. The core package stays usable without them.
- Workspace templates are packaged with the library so onboarding does not depend on private local files.
- The mock provider exists to keep demos runnable without API keys.
