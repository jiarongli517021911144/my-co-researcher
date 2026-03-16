from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from coresearcher.agent.context.token_counter import TokenCounter
from coresearcher.agent.memory import MemoryStore
from coresearcher.providers.base import LLMProvider


@dataclass(slots=True)
class MessageGroup:
    messages: list[dict[str, Any]]
    source_indices: list[int]
    token_count: int
    has_tool_calls: bool
    is_system: bool = False
    is_protected: bool = False


@dataclass(slots=True)
class CompressionResult:
    messages: list[dict[str, Any]]
    tokens_before: int
    tokens_after: int
    actions: list[str] = field(default_factory=list)
    flushed_history_count: int = 0
    new_last_consolidated: int | None = None


class ContextCompressor:
    def __init__(self, token_counter: TokenCounter, max_context_tokens: int, compression_ratio: float, summary_ratio: float) -> None:
        self.token_counter = token_counter
        self.max_context_tokens = max_context_tokens
        self.compression_ratio = compression_ratio
        self.summary_ratio = summary_ratio

    async def compress(
        self,
        messages: list[dict[str, Any]],
        provider: LLMProvider | None = None,
        *,
        memory_store: MemoryStore | None = None,
        session_key: str | None = None,
        history_count: int = 0,
        history_start: int = 0,
        last_consolidated: int = 0,
    ) -> CompressionResult:
        tokens_before = self.token_counter.count_messages(messages)
        normal_threshold = int(self.max_context_tokens * self.compression_ratio)
        summary_threshold = int(self.max_context_tokens * self.summary_ratio)
        if tokens_before <= normal_threshold:
            return CompressionResult(messages=list(messages), tokens_before=tokens_before, tokens_after=tokens_before)

        groups = self._group_by_tool_pairs(messages)
        kept_groups, dropped_groups = self._sliding_window_truncate(groups, normal_threshold)
        actions: list[str] = []
        flushed_history_count = 0
        new_last_consolidated: int | None = None

        if dropped_groups and memory_store is not None and session_key:
            flush_messages, flushed_history_count, new_last_consolidated = self._extract_flush_messages(
                messages,
                dropped_groups,
                history_count=history_count,
                history_start=history_start,
                last_consolidated=last_consolidated,
            )
            if flush_messages:
                logger.info(
                    "Memory flush triggered | session={} | reason=token_ratio>={:.0%} | tokens_before={} | threshold={} | dropped_groups={} | flush_count={} | last_consolidated={} | history_count={}",
                    session_key,
                    self.compression_ratio,
                    tokens_before,
                    normal_threshold,
                    len(dropped_groups),
                    len(flush_messages),
                    last_consolidated,
                    history_count,
                )
                await memory_store.flush_messages(session_key, flush_messages, provider=provider)
                actions.append(f"flush:{len(flush_messages)}")

        if dropped_groups:
            actions.append(f"trimmed_groups:{len(dropped_groups)}")

        compressed_messages = self._flatten_groups(kept_groups)
        tokens_after = self.token_counter.count_messages(compressed_messages)

        if tokens_after >= summary_threshold:
            kept_groups, summary_action = await self._apply_summary(kept_groups, provider, summary_threshold)
            if summary_action:
                actions.append(summary_action)
            compressed_messages = self._flatten_groups(kept_groups)
            tokens_after = self.token_counter.count_messages(compressed_messages)

        if tokens_after > self.max_context_tokens:
            compressed_messages = self._compact_system_messages(compressed_messages, self.max_context_tokens)
            tokens_after = self.token_counter.count_messages(compressed_messages)
            actions.append("compact_system")

        return CompressionResult(
            messages=compressed_messages,
            tokens_before=tokens_before,
            tokens_after=tokens_after,
            actions=actions,
            flushed_history_count=flushed_history_count,
            new_last_consolidated=new_last_consolidated,
        )

    def _group_by_tool_pairs(self, messages: list[dict[str, Any]]) -> list[MessageGroup]:
        groups: list[MessageGroup] = []
        idx = 0
        last_index = len(messages) - 1
        while idx < len(messages):
            message = messages[idx]
            role = message.get("role")
            if role == "system":
                groups.append(self._make_group([message], [idx], is_system=True, is_protected=False))
                idx += 1
                continue

            if role == "user":
                grouped_messages = [message]
                grouped_indices = [idx]
                idx += 1
                if idx < len(messages):
                    next_message = messages[idx]
                    if next_message.get("role") == "assistant" and next_message.get("tool_calls"):
                        grouped_messages.append(next_message)
                        grouped_indices.append(idx)
                        idx += 1
                        while idx < len(messages) and messages[idx].get("role") == "tool":
                            grouped_messages.append(messages[idx])
                            grouped_indices.append(idx)
                            idx += 1
                        if idx < len(messages) and messages[idx].get("role") == "assistant":
                            grouped_messages.append(messages[idx])
                            grouped_indices.append(idx)
                            idx += 1
                    elif next_message.get("role") == "assistant" and not next_message.get("tool_calls"):
                        grouped_messages.append(next_message)
                        grouped_indices.append(idx)
                        idx += 1
                groups.append(self._make_group(grouped_messages, grouped_indices, is_protected=last_index in grouped_indices))
                continue

            if role == "assistant" and message.get("tool_calls"):
                grouped_messages = [message]
                grouped_indices = [idx]
                idx += 1
                while idx < len(messages) and messages[idx].get("role") == "tool":
                    grouped_messages.append(messages[idx])
                    grouped_indices.append(idx)
                    idx += 1
                if idx < len(messages) and messages[idx].get("role") == "assistant":
                    grouped_messages.append(messages[idx])
                    grouped_indices.append(idx)
                    idx += 1
                groups.append(self._make_group(grouped_messages, grouped_indices, is_protected=last_index in grouped_indices))
                continue

            groups.append(self._make_group([message], [idx], is_protected=idx == last_index))
            idx += 1
        return groups

    def _sliding_window_truncate(self, groups: list[MessageGroup], target_tokens: int) -> tuple[list[MessageGroup], list[MessageGroup]]:
        kept = list(groups)
        dropped: list[MessageGroup] = []
        while self._groups_token_count(kept) > target_tokens:
            drop_index = next((i for i, group in enumerate(kept) if not group.is_system and not group.is_protected), None)
            if drop_index is None:
                break
            dropped.append(kept.pop(drop_index))
        return kept, dropped

    async def _apply_summary(
        self,
        groups: list[MessageGroup],
        provider: LLMProvider | None,
        summary_threshold: int,
    ) -> tuple[list[MessageGroup], str | None]:
        non_system_indices = [i for i, group in enumerate(groups) if not group.is_system]
        if len(non_system_indices) <= 2:
            return groups, None
        protected_tail = 2
        summarizable_positions = non_system_indices[:-protected_tail]
        if not summarizable_positions:
            return groups, None
        summary_groups = [groups[i] for i in summarizable_positions]
        summary_messages = self._flatten_groups(summary_groups)
        summary = await self._summarize(summary_messages, provider, max_summary_tokens=500)
        summary_message = {"role": "system", "content": f"[SUMMARY]\n{summary}"}
        summary_group = self._make_group([summary_message], [], is_system=True)
        new_groups = [group for i, group in enumerate(groups) if i not in summarizable_positions]
        insert_at = summarizable_positions[0]
        new_groups.insert(insert_at, summary_group)
        if self._groups_token_count(new_groups) > summary_threshold:
            return new_groups, "summary"
        return new_groups, "summary"

    def _extract_flush_messages(
        self,
        messages: list[dict[str, Any]],
        dropped_groups: list[MessageGroup],
        *,
        history_count: int,
        history_start: int,
        last_consolidated: int,
    ) -> tuple[list[dict[str, Any]], int, int | None]:
        non_system_indices = [i for i, msg in enumerate(messages) if msg.get("role") != "system"]
        history_indices = non_system_indices[:history_count]
        history_ordinal_by_index = {index: history_start + ordinal for ordinal, index in enumerate(history_indices)}
        selected_indices: list[int] = []
        selected_ordinals: list[int] = []
        for group in dropped_groups:
            for index in group.source_indices:
                ordinal = history_ordinal_by_index.get(index)
                if ordinal is None or ordinal < last_consolidated:
                    continue
                selected_indices.append(index)
                selected_ordinals.append(ordinal)
        selected_indices = sorted(dict.fromkeys(selected_indices))
        flush_messages = [messages[index] for index in selected_indices]
        new_last = max(selected_ordinals) + 1 if selected_ordinals else None
        return flush_messages, len(selected_indices), new_last

    async def _summarize(self, messages: list[dict[str, Any]], provider: LLMProvider | None, max_summary_tokens: int) -> str:
        transcript = []
        for message in messages:
            transcript.append(self._message_for_summary(message))
        raw = "\n".join(transcript)
        if provider is None:
            return self.token_counter.trim_text_to_tokens(raw, max_summary_tokens)
        summary_prompt = [
            {"role": "system", "content": "Summarize the following conversation into concise bullet points under 500 tokens. Preserve tool outcomes and decisions."},
            {"role": "user", "content": raw[:12000]},
        ]
        response = await provider.chat(summary_prompt)
        summary = response.content or raw
        return self.token_counter.trim_text_to_tokens(summary, max_summary_tokens)

    def _compact_system_messages(self, messages: list[dict[str, Any]], target_tokens: int) -> list[dict[str, Any]]:
        system_messages = [msg for msg in messages if msg.get("role") == "system"]
        non_system_messages = [msg for msg in messages if msg.get("role") != "system"]
        if not system_messages:
            return messages
        available_tokens = max(128, target_tokens - self.token_counter.count_messages(non_system_messages) - 16)
        combined = "\n\n".join(self.token_counter._flatten_content(msg.get("content")) for msg in system_messages)
        if len(combined) > 8000:
            combined = combined[:5000] + "\n...\n" + combined[-2000:]
        compact = self.token_counter.trim_text_to_tokens(f"[SYSTEM-SUMMARY]\n{combined}", available_tokens)
        return [{"role": "system", "content": compact}] + non_system_messages

    def _make_group(
        self,
        messages: list[dict[str, Any]],
        source_indices: list[int],
        *,
        is_system: bool = False,
        is_protected: bool = False,
    ) -> MessageGroup:
        return MessageGroup(
            messages=messages,
            source_indices=source_indices,
            token_count=self.token_counter.count_messages(messages),
            has_tool_calls=any(bool(message.get("tool_calls")) for message in messages),
            is_system=is_system,
            is_protected=is_protected,
        )

    def _groups_token_count(self, groups: list[MessageGroup]) -> int:
        return sum(group.token_count for group in groups)

    def _flatten_groups(self, groups: list[MessageGroup]) -> list[dict[str, Any]]:
        flattened: list[dict[str, Any]] = []
        for group in groups:
            flattened.extend(group.messages)
        return flattened

    def _message_for_summary(self, message: dict[str, Any]) -> str:
        role = message.get("role", "unknown")
        content = self.token_counter._flatten_content(message.get("content"))
        tool_calls = message.get("tool_calls") or []
        if tool_calls:
            tool_names = ", ".join((item.get("function") or {}).get("name", "unknown") for item in tool_calls)
            return f"{role} [tool_calls={tool_names}]: {content}"
        if role == "tool":
            return f"tool[{message.get('tool_call_id', '')}]: {content}"
        return f"{role}: {content}"
