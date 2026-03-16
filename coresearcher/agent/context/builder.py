from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from coresearcher.agent.skills.loader import SkillsLoader
from coresearcher.bus.events import InboundMessage
from coresearcher.config.schema import Config

_BOOTSTRAP_FILES = ["AGENTS.md", "SOUL.md", "USER.md", "IDENTITY.md", "TOOLS.md"]


class ContextBuilder:
    def __init__(
        self,
        config: Config,
        *,
        memory_store: Any | None = None,
        skills_loader: SkillsLoader | None = None,
    ) -> None:
        self.config = config
        self.memory_store = memory_store
        self.skills_loader = skills_loader

    async def build_messages(
        self,
        inbound: InboundMessage,
        history: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        system_sections = [self._identity_section(inbound), self._workspace_section()]

        history_sections: list[str] = []
        if self.memory_store is not None:
            long_term_memory = self.memory_store.read_long_term_memory()
            if long_term_memory:
                history_sections.append(f"[MEMORY.md]\n{long_term_memory}")

            recent_memory = self.memory_store.recent_daily_memories(self.config.memory.recent_days)
            if recent_memory:
                history_sections.append("[Recent Daily Memory]\n" + recent_memory)

            vector_results = self.memory_store.search(inbound.content, limit=self.config.memory.vector_top_k)
            if vector_results:
                formatted = "\n".join(
                    f"- ({item['score']:.2f}) {item['text']}" for item in vector_results
                )
                history_sections.append("[Vector Search Results]\n" + formatted)

        if history_sections:
            system_sections.append("History Context:\n" + "\n\n".join(history_sections))

        if self.skills_loader is not None:
            summary = self.skills_loader.describe_available_skills()
            if summary:
                system_sections.append("Available skills:\n" + summary)

        user_content = inbound.content
        if inbound.media:
            user_content += "\n\nAttachments:\n" + "\n".join(f"- {item}" for item in inbound.media)

        messages = [{"role": "system", "content": "\n\n".join(filter(None, system_sections))}]
        messages.extend(history or [])
        messages.append({"role": "user", "content": user_content})
        logger.info(
            "Context built | session={} | messages={}\n{}",
            inbound.session_key,
            len(messages),
            json.dumps(messages, ensure_ascii=False, indent=2),
        )
        return messages

    def _identity_section(self, inbound: InboundMessage) -> str:
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        return (
            f"Time: {now}\n"
            f"Workspace: {Path(self.config.workspace.path).expanduser()}\n"
            f"Channel: {inbound.channel}\n"
            f"Chat: {inbound.chat_id}"
        )

    def _workspace_section(self) -> str:
        workspace = Path(self.config.workspace.path).expanduser()
        parts: list[str] = []
        for name in _BOOTSTRAP_FILES:
            path = workspace / name
            if not path.exists():
                continue
            parts.append(f"[{name}]\n{path.read_text(encoding='utf-8')[:4000]}")
        return "\n\n".join(parts)
