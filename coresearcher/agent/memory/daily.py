from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path


class DailyMemory:
    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir).expanduser()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, day: date) -> Path:
        return self.base_dir / f"{day.isoformat()}.md"

    def append(self, summary: str, day: date | None = None, timestamp: datetime | None = None) -> Path:
        target_day = day or date.today()
        ts = timestamp or datetime.now()
        path = self.path_for(target_day)
        if not path.exists():
            path.write_text(f"# {target_day.isoformat()}\n\n", encoding="utf-8")

        normalized = self._normalize_summary(summary)
        entry = f"[{ts.strftime('%H:%M')}] {normalized}\n"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(entry)
        return path

    def read(self, day: date) -> str:
        path = self.path_for(day)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def read_recent(self, days: int = 1) -> str:
        chunks = [
            content.strip()
            for offset in range(days)
            if (content := self.read(date.today() - timedelta(days=offset))).strip()
        ]
        return "\n\n".join(chunks)

    def _normalize_summary(self, summary: str) -> str:
        text = summary.strip()
        text = text.replace("\r\n", "\n")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        collapsed = " ".join(lines)
        return collapsed[:1000]
