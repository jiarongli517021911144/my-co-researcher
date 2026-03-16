from __future__ import annotations

import json
from typing import Any

try:
    import tiktoken
except ImportError:  # pragma: no cover
    tiktoken = None


class TokenCounter:
    def __init__(self, model: str = "gpt-4o-mini") -> None:
        self.model = model
        self._encoding = None
        if tiktoken is not None:
            try:
                self._encoding = tiktoken.encoding_for_model(model)
            except Exception:
                self._encoding = tiktoken.get_encoding("cl100k_base")

    def count_text(self, text: str) -> int:
        if not text:
            return 0
        if self._encoding is None:
            return max(1, len(text) // 4)
        return len(self._encoding.encode(text))

    def count_message(self, message: dict[str, Any]) -> int:
        normalized = self._normalize_message(message)
        serialized = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
        return self.count_text(serialized) + 4

    def count_messages(self, messages: list[dict[str, Any]]) -> int:
        return sum(self.count_message(message) for message in messages)

    def trim_text_to_tokens(self, text: str, max_tokens: int) -> str:
        if max_tokens <= 0 or not text:
            return ""
        if self.count_text(text) <= max_tokens:
            return text
        if self._encoding is None:
            return text[: max(1, max_tokens * 4)]
        encoded = self._encoding.encode(text)
        trimmed = encoded[:max_tokens]
        return self._encoding.decode(trimmed)

    def _normalize_message(self, message: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        for key, value in message.items():
            if key == "content":
                normalized[key] = self._normalize_content(value)
            elif key == "tool_calls":
                normalized[key] = [self._normalize_tool_call(item) for item in value or []]
            elif isinstance(value, (str, int, float, bool)) or value is None:
                normalized[key] = value
            else:
                normalized[key] = self._stringify(value)
        return normalized

    def _normalize_tool_call(self, tool_call: Any) -> dict[str, Any]:
        if not isinstance(tool_call, dict):
            return {"raw": self._stringify(tool_call)}
        fn = tool_call.get("function") or {}
        arguments = fn.get("arguments")
        if isinstance(arguments, dict):
            arguments = json.dumps(arguments, ensure_ascii=False, sort_keys=True)
        return {
            "id": tool_call.get("id"),
            "type": tool_call.get("type"),
            "function": {
                "name": fn.get("name"),
                "arguments": arguments,
            },
        }

    def _normalize_content(self, content: Any) -> Any:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            normalized: list[dict[str, Any]] = []
            for item in content:
                if not isinstance(item, dict):
                    normalized.append({"raw": self._stringify(item)})
                    continue
                if item.get("type") == "text":
                    normalized.append({"type": "text", "text": item.get("text", "")})
                elif item.get("type") == "image_url":
                    normalized.append({"type": "image_url", "url": (item.get("image_url") or {}).get("url", "")})
                else:
                    normalized.append({k: self._stringify(v) if isinstance(v, (dict, list)) else v for k, v in item.items()})
            return normalized
        return self._stringify(content)

    def _flatten_content(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        chunks.append(item.get("text", ""))
                    elif item.get("type") == "image_url":
                        url = (item.get("image_url") or {}).get("url")
                        if url:
                            chunks.append(url)
            return "\n".join(chunks)
        return str(content or "")

    def _stringify(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        except Exception:
            return str(value)
