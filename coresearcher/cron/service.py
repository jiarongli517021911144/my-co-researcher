from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime

from coresearcher.cron.types import CronJob


class CronService:
    def __init__(self, handler: Callable[[CronJob], Awaitable[None] | None]) -> None:
        self.handler = handler
        self.jobs: dict[str, CronJob] = {}
        self._running = False

    def add_job(self, job: CronJob) -> None:
        if job.next_run is None:
            job.compute_next()
        self.jobs[job.name] = job

    def remove_job(self, name: str) -> bool:
        if name in self.jobs:
            del self.jobs[name]
            return True
        return False

    async def run_pending(self, now: datetime | None = None) -> None:
        current = now or datetime.now()
        for job in self.jobs.values():
            if job.next_run is None:
                job.compute_next(current)
            if job.next_run and job.next_run <= current:
                try:
                    result = self.handler(job)
                    if hasattr(result, "__await__"):
                        await result
                    job.failures = 0
                    job.last_error = None
                except Exception as exc:  # pragma: no cover
                    job.failures += 1
                    job.last_error = str(exc)
                finally:
                    job.compute_next(current)

    async def serve(self, interval_seconds: int = 30) -> None:
        self._running = True
        while self._running:
            await self.run_pending()
            await asyncio.sleep(interval_seconds)

    def stop(self) -> None:
        self._running = False
