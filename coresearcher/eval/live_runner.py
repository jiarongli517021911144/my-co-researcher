from __future__ import annotations

import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

from coresearcher.agent.loop import AgentLoop
from coresearcher.agent.memory import MemoryStore
from coresearcher.bus import InboundMessage, MessageBus
from coresearcher.config import Config
from coresearcher.eval.types import EvalRunResult, EvalTask
from coresearcher.providers.factory import create_provider
from coresearcher.session import SessionManager


class LiveAgentEvalRunner:
    def __init__(self, config: Config, *, work_dir: str | Path = "eval/runtime") -> None:
        self.config = config
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)

    async def run_task(self, task: EvalTask) -> EvalRunResult:
        task_dir = self.work_dir / task.id
        if task_dir.exists():
            shutil.rmtree(task_dir)
        task_dir.mkdir(parents=True, exist_ok=True)

        runtime_config = self._build_task_config(task_dir)
        provider = create_provider(runtime_config)
        session_manager = SessionManager(task_dir / "sessions")
        memory_store = MemoryStore(task_dir / "workspace" / "memory")
        loop = AgentLoop(
            runtime_config,
            MessageBus(),
            provider,
            session_manager=session_manager,
            memory_store=memory_store,
        )
        trace_events: list[dict[str, Any]] = []
        outbound = await loop._process_message(
            InboundMessage(
                channel="cli",
                sender_id="eval",
                chat_id=task.id,
                content=task.prompt,
                metadata={"eval_task_id": task.id},
            ),
            trace_events=trace_events,
            publish_outbound=False,
        )
        trace = self._render_trace(trace_events)
        return EvalRunResult(
            output=outbound.content,
            trace=trace,
            metadata={
                "events": trace_events,
                "task_dir": str(task_dir),
                "workspace": str(Path(runtime_config.workspace.path).expanduser()),
            },
        )

    def _build_task_config(self, task_dir: Path) -> Config:
        runtime_config = Config.model_validate(self.config.model_dump(mode="json"))
        src_workspace = Path(self.config.workspace.path).expanduser()
        dst_workspace = task_dir / "workspace"
        if src_workspace.exists():
            shutil.copytree(src_workspace, dst_workspace)
        else:
            dst_workspace.mkdir(parents=True, exist_ok=True)
        runtime_config.workspace.path = str(dst_workspace)
        runtime_config.tools.allowed_dir = str(dst_workspace)
        runtime_config.memory.directory = str(dst_workspace / "memory")
        runtime_config.memory.session_dir = str(task_dir / "sessions")
        runtime_config.cron.store_path = str(task_dir / "cron_jobs.json")
        runtime_config.channels.cli.enabled = False
        runtime_config.channels.qq.enabled = False
        runtime_config.channels.feishu.enabled = False
        runtime_config.agents.enable_reflexion = False
        runtime_config.agents.reflexion.enabled = False
        return runtime_config

    def _render_trace(self, events: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        pending_tool: dict[str, Any] | None = None
        for event in events:
            kind = event.get("kind", "event")
            if kind == "plan_generated":
                lines.append(f"PLAN GENERATED\n{event.get('plan')}")
            elif kind == "plan_batch":
                lines.append(f"PLAN BATCH steps={event.get('steps')} parallelism={event.get('parallelism')}")
            elif kind == "plan_step_finished":
                lines.append(f"PLAN STEP {event.get('step_id')} status={event.get('status')} result={event.get('result')}")
            elif kind == "plan_replanned":
                lines.append(f"PLAN REPLANNED reason={event.get('reason')}\n{event.get('plan')}")
            elif kind == "tool_call":
                pending_tool = event
            elif kind == "tool_result":
                if pending_tool is not None and pending_tool.get("tool") == event.get("tool"):
                    lines.append(f"TOOL {event.get('tool')} args={pending_tool.get('args')} result={event.get('result')}")
                    pending_tool = None
                else:
                    lines.append(f"TOOL_RESULT {event.get('tool')} result={event.get('result')}")
            elif kind == "reflexion_critic":
                lines.append(f"CRITIC attempt={event.get('attempt')} score={event.get('score')} passed={event.get('passed')} feedback={event.get('feedback')}")
            elif kind == "final_response":
                lines.append(f"FINAL RESPONSE {event.get('content')}")
        if pending_tool is not None:
            lines.append(f"TOOL {pending_tool.get('tool')} args={pending_tool.get('args')}")
        return "\n".join(lines)
