from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import uvicorn
from starlette.applications import Starlette
from starlette.endpoints import WebSocketEndpoint
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles

from coresearcher.agent.loop import AgentLoop
from coresearcher.agent.memory import MemoryStore
from coresearcher.bus import InboundMessage, MessageBus
from coresearcher.config import default_config_path, load_config, save_config
from coresearcher.config.schema import Config
from coresearcher.cron import CronStore
from coresearcher.providers.factory import create_provider
from coresearcher.session import SessionManager


STATIC_DIR = Path(__file__).with_name("static")
PAGE_FILES = {
    "dashboard": "index.html",
    "chat": "chat.html",
    "workspace": "workspace.html",
    "sessions": "sessions.html",
    "memory": "memory.html",
    "config": "config.html",
}


def create_app() -> Starlette:
    routes = [
        Route("/", endpoint=index, methods=["GET"]),
        Route("/chat", endpoint=chat_page, methods=["GET"]),
        Route("/workspace", endpoint=workspace_page, methods=["GET"]),
        Route("/sessions", endpoint=sessions_page, methods=["GET"]),
        Route("/memory", endpoint=memory_page, methods=["GET"]),
        Route("/config", endpoint=config_page, methods=["GET"]),
        Route("/api/state", endpoint=get_state, methods=["GET"]),
        Route("/api/file", endpoint=file_endpoint, methods=["GET", "PUT"]),
        Route("/api/config", endpoint=config_endpoint, methods=["GET", "PUT"]),
        Route("/api/sessions", endpoint=sessions_endpoint, methods=["GET"]),
        Route("/api/session/{session_id:path}", endpoint=session_endpoint, methods=["GET"]),
        Route("/api/memory-search", endpoint=memory_search_endpoint, methods=["GET"]),
        Route("/api/memory-recent", endpoint=memory_recent_endpoint, methods=["GET"]),
        Route("/api/cron", endpoint=cron_endpoint, methods=["GET"]),
        WebSocketRoute("/ws/chat", endpoint=ChatTraceEndpoint),
        Mount("/static", app=StaticFiles(directory=str(STATIC_DIR)), name="static"),
    ]
    return Starlette(debug=True, routes=routes)


def _serve_page(page_name: str) -> FileResponse:
    return FileResponse(STATIC_DIR / PAGE_FILES[page_name])


def _display_path(path: Path) -> str:
    try:
        home = Path.home().resolve()
        resolved = path.expanduser().resolve()
        if resolved == home:
            return "~"
        if home in resolved.parents:
            rel = resolved.relative_to(home)
            return f"~/{rel.as_posix()}"
        return resolved.as_posix()
    except Exception:
        return str(path)


async def index(request: Request) -> FileResponse:
    return _serve_page("dashboard")


async def chat_page(request: Request) -> FileResponse:
    return _serve_page("chat")


async def workspace_page(request: Request) -> FileResponse:
    return _serve_page("workspace")


async def sessions_page(request: Request) -> FileResponse:
    return _serve_page("sessions")


async def memory_page(request: Request) -> FileResponse:
    return _serve_page("memory")


async def config_page(request: Request) -> FileResponse:
    return _serve_page("config")


async def get_state(request: Request) -> JSONResponse:
    config = load_config()
    workspace = Path(config.workspace.path).expanduser()
    memory_dir = Path(config.memory.directory).expanduser()
    return JSONResponse(
        {
            "config_path": _display_path(default_config_path()),
            "workspace": _display_path(workspace),
            "memory_dir": _display_path(memory_dir),
            "session_dir": _display_path(Path(config.memory.session_dir).expanduser()),
            "workspace_files": _list_workspace_files(workspace),
            "config": config.model_dump(mode="json", exclude_none=True),
        }
    )


async def file_endpoint(request: Request) -> JSONResponse:
    config = load_config()
    workspace = Path(config.workspace.path).expanduser().resolve()
    if request.method == "GET":
        relative = request.query_params.get("path") or ""
        try:
            path = _resolve_workspace_path(workspace, relative)
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        if not path.exists() or not path.is_file():
            return JSONResponse({"error": "file not found"}, status_code=404)
        return JSONResponse({"path": relative, "content": path.read_text(encoding="utf-8")})

    payload = await request.json()
    relative = payload.get("path") or ""
    content = payload.get("content") or ""
    try:
        path = _resolve_workspace_path(workspace, relative)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return JSONResponse({"ok": True, "path": relative})


async def config_endpoint(request: Request) -> JSONResponse:
    config_path = default_config_path()
    if request.method == "GET":
        if not config_path.exists():
            return JSONResponse({"content": "{}\n"})
        return JSONResponse({"content": config_path.read_text(encoding="utf-8")})

    payload = await request.json()
    raw = payload.get("content") or "{}"
    data = json.loads(raw)
    config = Config.model_validate(data)
    save_config(config, config_path)
    return JSONResponse({"ok": True})


async def sessions_endpoint(request: Request) -> JSONResponse:
    config = load_config()
    limit = max(1, int(request.query_params.get("limit") or 50))
    sessions_dir = Path(config.memory.session_dir).expanduser()
    return JSONResponse({"sessions": _list_sessions(sessions_dir, limit=limit)})


async def session_endpoint(request: Request) -> JSONResponse:
    config = load_config()
    session_id = request.path_params["session_id"]
    limit = max(1, int(request.query_params.get("limit") or 100))
    sessions = SessionManager(config.memory.session_dir)
    window = sessions.load_recent_window(session_id, limit)
    return JSONResponse(
        {
            "session_id": session_id,
            "messages": window.messages,
            "start_index": window.start_index,
            "total_count": window.total_count,
            "last_consolidated": sessions.get_last_consolidated(session_id),
        }
    )


async def memory_search_endpoint(request: Request) -> JSONResponse:
    config = load_config()
    query = request.query_params.get("q") or ""
    limit = max(1, int(request.query_params.get("limit") or 10))
    store = MemoryStore(config.memory.directory)
    return JSONResponse({"results": store.search(query, limit=limit)})


async def memory_recent_endpoint(request: Request) -> JSONResponse:
    config = load_config()
    days = max(1, int(request.query_params.get("days") or 7))
    memory_dir = Path(config.memory.directory).expanduser()
    return JSONResponse({"entries": _list_memory_entries(memory_dir, days=days)})


async def cron_endpoint(request: Request) -> JSONResponse:
    config = load_config()
    store = CronStore(config.cron.store_path)
    jobs = [
        {"name": job.name, "schedule": job.schedule, "payload": job.payload}
        for job in store.load()
    ]
    return JSONResponse({"jobs": jobs})


class ChatTraceEndpoint(WebSocketEndpoint):
    encoding = "json"

    async def on_connect(self, websocket) -> None:
        await websocket.accept()

    async def on_receive(self, websocket, data: dict[str, Any]) -> None:
        config = load_config()
        provider = create_provider(config)
        sessions = SessionManager(config.memory.session_dir)
        memory_store = MemoryStore(config.memory.directory)
        loop = AgentLoop(config, MessageBus(), provider, session_manager=sessions, memory_store=memory_store)
        session_id = str(data.get("session_id") or "web-default")
        message = str(data.get("message") or "").strip()
        if not message:
            await websocket.send_json({"kind": "error", "message": "empty message"})
            return

        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        def sink(event: dict[str, Any]) -> None:
            queue.put_nowait(event)

        loop.subagents.add_listener(sink)
        sink(loop.subagents.snapshot())

        async def run_agent() -> None:
            try:
                await loop._process_message(
                    InboundMessage(channel="web", sender_id="web-user", chat_id=session_id, content=message),
                    trace_events=[],
                    trace_sink=sink,
                    publish_outbound=False,
                )
            finally:
                loop.subagents.remove_listener(sink)

        task = asyncio.create_task(run_agent())
        try:
            while True:
                if task.done() and queue.empty():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.2)
                    await websocket.send_json(event)
                except asyncio.TimeoutError:
                    continue
            await task
            await websocket.send_json({"kind": "done"})
        except Exception as exc:
            await websocket.send_json({"kind": "error", "message": f"{type(exc).__name__}: {exc}"})

    async def on_disconnect(self, websocket, close_code) -> None:
        return None


def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    uvicorn.run(create_app(), host=host, port=port, log_level="info")


def _resolve_workspace_path(workspace: Path, relative: str) -> Path:
    path = (workspace / relative).resolve()
    if workspace not in {path, *path.parents}:
        raise ValueError("path outside workspace")
    return path


def _list_workspace_files(workspace: Path) -> list[str]:
    files = []
    for path in sorted(workspace.rglob("*")):
        if path.is_file() and ".chroma" not in path.parts and "__pycache__" not in path.parts:
            files.append(str(path.relative_to(workspace)))
    return files


def _restore_session_id(stem: str) -> str:
    return stem.replace("__", ":")


def _session_preview(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        role = message.get("role")
        content = str(message.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            compact = " ".join(content.split())
            return compact[:120]
    return ""


def _list_sessions(sessions_dir: Path, limit: int = 50) -> list[dict[str, Any]]:
    if not sessions_dir.exists():
        return []
    payload: list[dict[str, Any]] = []
    for path in sorted(sessions_dir.glob("*.jsonl"), key=lambda item: item.stat().st_mtime, reverse=True):
        records: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except Exception:
                continue
        session_id = _restore_session_id(path.stem)
        state_path = path.with_suffix("").with_suffix(".state.json")
        last_consolidated = 0
        if state_path.exists():
            try:
                last_consolidated = int(json.loads(state_path.read_text(encoding="utf-8")).get("last_consolidated", 0))
            except Exception:
                last_consolidated = 0
        payload.append(
            {
                "session_id": session_id,
                "total_count": len(records),
                "last_consolidated": last_consolidated,
                "updated_at": datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds"),
                "preview": _session_preview(records),
            }
        )
        if len(payload) >= limit:
            break
    return payload


def _list_memory_entries(memory_dir: Path, days: int = 7) -> list[dict[str, Any]]:
    if not memory_dir.exists():
        return []
    entries: list[dict[str, Any]] = []
    for path in sorted(memory_dir.glob("*.md"), reverse=True):
        if path.name == "MEMORY.md":
            continue
        stem = path.stem
        if len(stem) != 10:
            continue
        content = path.read_text(encoding="utf-8").strip()
        lines = [line for line in content.splitlines() if line.strip()]
        entries.append(
            {
                "date": stem,
                "path": _display_path(path),
                "line_count": len(lines),
                "preview": " ".join(lines[1:3])[:180] if len(lines) > 1 else content[:180],
                "content": content,
            }
        )
        if len(entries) >= days:
            break
    return entries
