from __future__ import annotations

from pathlib import Path
from typing import Any

from coresearcher.agent.tools.base import Tool


class _FilesystemTool(Tool):
    def __init__(self, allowed_dir: str, restrict_to_workspace: bool) -> None:
        self.allowed_dir = Path(allowed_dir).expanduser().resolve()
        self.restrict_to_workspace = restrict_to_workspace

    def _resolve(self, path_value: str) -> Path:
        path = Path(path_value).expanduser()
        if not path.is_absolute():
            path = self.allowed_dir / path
        resolved = path.resolve()
        if self.restrict_to_workspace and self.allowed_dir not in {resolved, *resolved.parents}:
            raise PermissionError(f"Path outside allowed workspace: {resolved}")
        return resolved

    def _error(self, message: str) -> str:
        return f"Error: {message}"


class ReadFileTool(_FilesystemTool):
    name = "read"
    description = "Read a UTF-8 text file"
    parameters = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    }

    async def execute(self, arguments: dict[str, Any]) -> str:
        try:
            path = self._resolve(arguments["path"])
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return self._error(f"file not found: {arguments['path']}")
        except Exception as exc:
            return self._error(str(exc))


class WriteFileTool(_FilesystemTool):
    name = "write"
    description = "Write UTF-8 text to a file"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["path", "content"],
    }

    async def execute(self, arguments: dict[str, Any]) -> str:
        try:
            path = self._resolve(arguments["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(arguments["content"], encoding="utf-8")
            return f"wrote {path}"
        except Exception as exc:
            return self._error(str(exc))


class EditFileTool(_FilesystemTool):
    name = "edit_file"
    description = "Replace text in a file"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "old": {"type": "string"},
            "new": {"type": "string"},
        },
        "required": ["path", "old", "new"],
    }

    async def execute(self, arguments: dict[str, Any]) -> str:
        try:
            path = self._resolve(arguments["path"])
            content = path.read_text(encoding="utf-8")
            updated = content.replace(arguments["old"], arguments["new"], 1)
            if updated == content:
                return "pattern not found"
            path.write_text(updated, encoding="utf-8")
            return f"updated {path}"
        except FileNotFoundError:
            return self._error(f"file not found: {arguments['path']}")
        except Exception as exc:
            return self._error(str(exc))


class ListDirTool(_FilesystemTool):
    name = "list_dir"
    description = "List files under a directory"
    parameters = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": [],
    }

    async def execute(self, arguments: dict[str, Any]) -> list[str] | str:
        try:
            path = self._resolve(arguments.get("path") or ".")
            return sorted(item.name for item in path.iterdir())
        except FileNotFoundError:
            return self._error(f"directory not found: {arguments.get('path') or '.'}")
        except Exception as exc:
            return self._error(str(exc))
