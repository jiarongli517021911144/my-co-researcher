from __future__ import annotations

import json
from pathlib import Path

from coresearcher.cron.types import CronJob


class CronStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> list[CronJob]:
        if not self.path.exists():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        jobs = []
        for item in payload:
            jobs.append(CronJob(name=item["name"], schedule=item["schedule"], payload=item.get("payload", {})))
        return jobs

    def save(self, jobs: list[CronJob]) -> None:
        payload = [{"name": job.name, "schedule": job.schedule, "payload": job.payload} for job in jobs]
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def add(self, job: CronJob) -> None:
        jobs = {item.name: item for item in self.load()}
        jobs[job.name] = job
        self.save(list(jobs.values()))

    def remove(self, name: str) -> bool:
        jobs = {item.name: item for item in self.load()}
        existed = name in jobs
        jobs.pop(name, None)
        self.save(list(jobs.values()))
        return existed
