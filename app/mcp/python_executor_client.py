from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from app.mcp.filesystem_client import MCPClientError, FilesystemMCPClient

logger = logging.getLogger(__name__)


@dataclass
class PythonExecutorToolBinding:
    execute_tool: str


class PythonExecutorMCPClient(FilesystemMCPClient):
    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 30.0,
        execute_tool_name: str | None = None,
    ) -> None:
        super().__init__(base_url=base_url, timeout_seconds=timeout_seconds)
        self._exec_binding = PythonExecutorToolBinding(
            execute_tool=execute_tool_name or os.getenv("MCP_PYTHON_EXEC_TOOL", "execute_python"),
        )

    def discover_tools(self) -> PythonExecutorToolBinding:
        logger.info("python_executor:tool_discovery_start")
        response = self._rpc("tools/list")
        tools = response.get("tools", [])
        names = {tool.get("name") for tool in tools if isinstance(tool, dict)}

        execute_tool = self._exec_binding.execute_tool
        if execute_tool not in names:
            execute_tool = self._find_candidate(
                names,
                ["execute_python", "python_exec", "run_python", "execute", "run_command"],
            )

        if not execute_tool:
            raise MCPClientError(f"Unable to bind python executor tool. Available: {sorted(names)}")

        self._exec_binding = PythonExecutorToolBinding(execute_tool=execute_tool)
        logger.info("python_executor:tool_binding_success execute_tool=%s", execute_tool)
        return self._exec_binding

    def execute_python(self, code: str) -> dict[str, Any]:
        logger.info("python_executor:execute_python_start size=%s", len(code))
        return self._call_execute({"code": code})

    def execute_command(self, command: str) -> dict[str, Any]:
        logger.info("python_executor:execute_command_start command=%s", command)
        return self._call_execute({"command": command})

    def _call_execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        result = self._rpc(
            "tools/call",
            {
                "name": self._exec_binding.execute_tool,
                "arguments": arguments,
            },
        )
        if result.get("isError"):
            raise MCPClientError(f"Python executor failed: {result}")
        normalized = self._normalize_result(result)
        logger.info(
            "python_executor:execute_done exit_code=%s stdout_len=%s stderr_len=%s",
            normalized.get("exit_code", "unknown"),
            len(normalized.get("stdout", "")),
            len(normalized.get("stderr", "")),
        )
        return normalized

    @staticmethod
    def _normalize_result(result: dict[str, Any]) -> dict[str, Any]:
        if isinstance(result.get("structuredContent"), dict):
            content = result["structuredContent"]
            return {
                "stdout": str(content.get("stdout", "")),
                "stderr": str(content.get("stderr", "")),
                "exit_code": content.get("exit_code", 0),
            }
        text = FilesystemMCPClient._extract_content(result)
        return {"stdout": text, "stderr": "", "exit_code": 0}
