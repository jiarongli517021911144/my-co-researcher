
from __future__ import annotations

import asyncio
import shlex
from typing import Any

from coresearcher.agent.tools.base import Tool

_BLOCKED_TOKENS = {"rm -rf /", "shutdown", "reboot", ":(){:|:&};:"}


class ExecTool(Tool):
    name = "exec"
    description = "Execute a shell command with timeout and safety checks"
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string"},
            "timeout": {"type": "integer", "minimum": 1},
        },
        "required": ["command"],
    }

    def __init__(self, timeout_seconds: int = 30) -> None:
        self.timeout_seconds = timeout_seconds

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        command = arguments["command"].strip()
        if any(token in command for token in _BLOCKED_TOKENS):
            raise PermissionError("Blocked dangerous command")

        timeout = int(arguments.get("timeout") or self.timeout_seconds)
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            return {"ok": False, "stdout": "", "stderr": f"timeout after {timeout}s", "code": -1}

        return {
            "ok": process.returncode == 0,
            "stdout": stdout.decode("utf-8", "ignore"),
            "stderr": stderr.decode("utf-8", "ignore"),
            "code": process.returncode,
            "argv": shlex.split(command),
        }
