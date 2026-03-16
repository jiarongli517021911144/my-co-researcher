from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from typing import Any


class SubagentManager:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._listeners: list[Callable[[dict[str, Any]], None]] = []
        self._total_spawned = 0
        self._completed = 0

    def add_listener(self, listener: Callable[[dict[str, Any]], None]) -> None:
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[dict[str, Any]], None]) -> None:
        self._listeners = [item for item in self._listeners if item is not listener]

    def snapshot(self) -> dict[str, Any]:
        return {
            "kind": "subagent_status",
            "phase": "snapshot",
            "active_count": len(self._tasks),
            "total_spawned": self._total_spawned,
            "completed_count": self._completed,
            "task_ids": sorted(self._tasks),
        }

    def spawn(self, factory: Callable[[], Awaitable[Any]], name: str | None = None) -> str:
        task_id = name or f"subagent-{uuid.uuid4().hex[:8]}"
        task = asyncio.create_task(factory(), name=task_id)
        self._tasks[task_id] = task
        self._total_spawned += 1
        self._emit({
            "kind": "subagent_status",
            "phase": "spawned",
            "task_id": task_id,
            "active_count": len(self._tasks),
            "total_spawned": self._total_spawned,
            "completed_count": self._completed,
            "task_ids": sorted(self._tasks),
        })
        task.add_done_callback(lambda finished: self._on_task_done(task_id, finished))
        return task_id

    def list(self) -> list[str]:
        return sorted(self._tasks)

    async def cancel_all(self) -> None:
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()
        self._emit({
            "kind": "subagent_status",
            "phase": "cancel_all",
            "active_count": len(self._tasks),
            "total_spawned": self._total_spawned,
            "completed_count": self._completed,
            "task_ids": [],
        })

    def _on_task_done(self, task_id: str, task: asyncio.Task[Any]) -> None:
        self._tasks.pop(task_id, None)
        phase = "completed"
        error = None
        if task.cancelled():
            phase = "cancelled"
        else:
            try:
                task.result()
            except Exception as exc:
                phase = "failed"
                error = f"{type(exc).__name__}: {exc}"
        self._completed += 1
        payload = {
            "kind": "subagent_status",
            "phase": phase,
            "task_id": task_id,
            "active_count": len(self._tasks),
            "total_spawned": self._total_spawned,
            "completed_count": self._completed,
            "task_ids": sorted(self._tasks),
        }
        if error:
            payload["error"] = error
        self._emit(payload)

    def _emit(self, payload: dict[str, Any]) -> None:
        for listener in list(self._listeners):
            try:
                listener(dict(payload))
            except Exception:
                continue
