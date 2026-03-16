from __future__ import annotations

from pathlib import Path

from coresearcher.bus.events import InboundMessage

DEFAULT_PROMPT = (
    "Read HEARTBEAT.md if it exists (workspace context). Follow it strictly. "
    "Do not infer or repeat old tasks from prior chats. If nothing needs attention, reply HEARTBEAT_OK."
)


class HeartbeatService:
    def __init__(self, workspace_path: str | Path, prompt: str = DEFAULT_PROMPT) -> None:
        self.workspace_path = Path(workspace_path).expanduser()
        self.prompt = prompt

    def read_task(self) -> str | None:
        path = self.workspace_path / "HEARTBEAT.md"
        if not path.exists():
            return None
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            return None
        return content

    def build_inbound_message(self, channel: str = "cli", chat_id: str = "heartbeat") -> InboundMessage | None:
        task = self.read_task()
        if not task:
            return None
        return InboundMessage(channel=channel, sender_id="heartbeat", chat_id=chat_id, content=f"{self.prompt}\n\n{task}")
