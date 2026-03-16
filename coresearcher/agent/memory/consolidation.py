from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger

from coresearcher.providers.base import LLMProvider


class MemoryFlusher:
    def __init__(self, daily_memory, vector_index) -> None:
        self.daily_memory = daily_memory
        self.vector_index = vector_index

    async def flush(self, session_key: str, messages: list[dict[str, Any]], provider: LLMProvider | None = None) -> str:
        if not messages:
            return ""
        transcript = "\n".join(f"{msg.get('role')}: {msg.get('content')}" for msg in messages)
        summary = transcript[:2000]
        if provider is not None:
            response = await provider.chat(
                [
                    {
                        "role": "system",
                        "content": (
                            "Summarize the conversation into 2-5 factual Chinese sentences suitable for a daily journal line. "
                            "Do not include markdown headers or bullet points."
                        ),
                    },
                    {"role": "user", "content": transcript[:12000]},
                ]
            )
            summary = response.content or summary

        normalized = self.daily_memory._normalize_summary(summary)
        logger.info(
            "Memory flushed to disk | session={} | summary={} | source_messages={} | transcript_preview={}",
            session_key,
            normalized[:500],
            len(messages),
            transcript[:300],
        )
        self.daily_memory.append(normalized, timestamp=datetime.now())
        self.vector_index.add(normalized, {"session_key": session_key})
        return normalized
