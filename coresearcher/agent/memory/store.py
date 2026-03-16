from __future__ import annotations

from pathlib import Path

from coresearcher.agent.memory.consolidation import MemoryFlusher
from coresearcher.agent.memory.daily import DailyMemory
from coresearcher.agent.memory.vector import VectorIndex


class MemoryStore:
    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir).expanduser()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.workspace_dir = self.base_dir.parent
        self.daily = DailyMemory(self.base_dir)
        self.vector = VectorIndex(self.base_dir / ".chroma")
        self.flusher = MemoryFlusher(self.daily, self.vector)

    def long_term_memory_path(self) -> Path:
        root_path = self.workspace_dir / "MEMORY.md"
        if root_path.exists():
            return root_path
        legacy_path = self.base_dir / "MEMORY.md"
        return legacy_path

    def read_long_term_memory(self) -> str:
        path = self.long_term_memory_path()
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def add_note(self, content: str, metadata: dict | None = None) -> None:
        self.daily.append(content)
        self.vector.add(content, metadata)

    def search(self, query: str, limit: int = 5) -> list[dict]:
        return self.vector.search(query, limit=limit)

    def recent_daily_memories(self, days: int = 1) -> str:
        return self.daily.read_recent(days)

    async def flush_messages(self, session_key: str, messages: list[dict], provider=None) -> str:
        return await self.flusher.flush(session_key, messages, provider=provider)
