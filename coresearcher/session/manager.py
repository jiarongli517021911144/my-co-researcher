from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SessionWindow:
    messages: list[dict[str, Any]]
    start_index: int
    total_count: int


def _safe_session_filename(session_key: str) -> str:
    return session_key.replace(":", "__").replace("/", "_")


class SessionManager:
    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir).expanduser()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def session_path(self, session_key: str) -> Path:
        return self.base_dir / f"{_safe_session_filename(session_key)}.jsonl"

    def state_path(self, session_key: str) -> Path:
        return self.base_dir / f"{_safe_session_filename(session_key)}.state.json"

    def load_messages(self, session_key: str) -> list[dict[str, Any]]:
        path = self.session_path(session_key)
        if not path.exists():
            return []
        records: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            records.append(json.loads(line))
        return records

    def load_recent_window(self, session_key: str, limit: int) -> SessionWindow:
        path = self.session_path(session_key)
        if not path.exists():
            return SessionWindow(messages=[], start_index=0, total_count=0)
        window: deque[dict[str, Any]] = deque(maxlen=max(1, limit))
        total_count = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            window.append(json.loads(line))
            total_count += 1
        start_index = max(0, total_count - len(window))
        return SessionWindow(messages=list(window), start_index=start_index, total_count=total_count)

    def load_message_range(self, session_key: str, start: int, end: int | None = None) -> list[dict[str, Any]]:
        path = self.session_path(session_key)
        if not path.exists():
            return []
        if end is not None and end <= start:
            return []
        records: list[dict[str, Any]] = []
        for index, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            if index < start:
                continue
            if end is not None and index >= end:
                break
            records.append(json.loads(line))
        return records

    def append_message(self, session_key: str, message: dict[str, Any]) -> None:
        path = self.session_path(session_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(message, ensure_ascii=False) + "\n")

    def append_messages(self, session_key: str, messages: list[dict[str, Any]]) -> None:
        for message in messages:
            self.append_message(session_key, message)

    def get_last_consolidated(self, session_key: str) -> int:
        path = self.state_path(session_key)
        if not path.exists():
            return 0
        payload = json.loads(path.read_text(encoding="utf-8"))
        return int(payload.get("last_consolidated", 0))

    def set_last_consolidated(self, session_key: str, index: int) -> None:
        path = self.state_path(session_key)
        path.write_text(json.dumps({"last_consolidated": index}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
