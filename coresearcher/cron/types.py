from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from croniter import croniter


@dataclass(slots=True)
class CronJob:
    name: str
    schedule: str
    payload: dict
    next_run: datetime | None = None
    failures: int = 0
    last_error: str | None = None

    def compute_next(self, now: datetime | None = None) -> datetime:
        base = now or datetime.now()
        self.next_run = croniter(self.schedule, base).get_next(datetime)
        return self.next_run
