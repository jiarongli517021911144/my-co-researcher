from __future__ import annotations

from typing import Any

from coresearcher.providers.base import LLMProvider, LLMResponse, ToolCallRequest


class MockProvider(LLMProvider):
    def __init__(self, default_model: str = "mock/default") -> None:
        super().__init__(api_key=None, api_base=None)
        self.default_model = default_model

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        last = messages[-1] if messages else {"role": "user", "content": ""}
        if last.get("role") == "tool":
            return LLMResponse(content=f"Tool result received: {last.get('content', '')[:400]}")

        user_text = str(last.get("content", ""))
        if tools and any(keyword in user_text.lower() for keyword in ["ls", "list dir", "列出目录"]):
            return LLMResponse(
                content=None,
                tool_calls=[ToolCallRequest(id="mock-call-1", name="list_dir", arguments={"path": "."})],
            )
        if tools and any(keyword in user_text.lower() for keyword in ["read", "读取文件"]):
            return LLMResponse(
                content=None,
                tool_calls=[ToolCallRequest(id="mock-call-2", name="read", arguments={"path": "AGENTS.md"})],
            )
        return LLMResponse(content=f"[mock:{model or self.default_model}] {user_text}")

    def get_default_model(self) -> str:
        return self.default_model
