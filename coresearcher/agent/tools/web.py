from __future__ import annotations

from typing import Any

import httpx

from coresearcher.agent.tools.base import Tool


class WebSearchTool(Tool):
    name = "web_search"
    description = "Search the web using Brave Search API"
    parameters = {
        "type": "object",
        "properties": {"query": {"type": "string"}, "count": {"type": "integer", "minimum": 1}},
        "required": ["query"],
    }

    def __init__(self, api_key: str | None, base_url: str, max_results: int = 5) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.max_results = max_results

    async def execute(self, arguments: dict[str, Any]) -> Any:
        if not self.api_key:
            return {"ok": False, "error": "Brave API key not configured"}

        params = {"q": arguments["query"], "count": min(int(arguments.get("count") or self.max_results), self.max_results)}
        headers = {"X-Subscription-Token": self.api_key, "Accept": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(self.base_url, params=params, headers=headers)
                response.raise_for_status()
                payload = response.json()
            results = payload.get("web", {}).get("results", [])
            return [
                {"title": item.get("title"), "url": item.get("url"), "description": item.get("description")}
                for item in results[: params["count"]]
            ]
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "query": arguments["query"]}


class WebFetchTool(Tool):
    name = "web_fetch"
    description = "Fetch a web page as text"
    parameters = {
        "type": "object",
        "properties": {"url": {"type": "string"}},
        "required": ["url"],
    }

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                response = await client.get(arguments["url"])
                response.raise_for_status()
            return {"ok": True, "url": str(response.url), "status": response.status_code, "text": response.text[:10000]}
        except Exception as exc:
            return {"ok": False, "url": arguments["url"], "error": f"{type(exc).__name__}: {exc}"}
