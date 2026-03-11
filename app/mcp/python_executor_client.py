from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from app.mcp.filesystem_client import MCPClientError, FilesystemMCPClient

logger = logging.getLogger(__name__)


@dataclass
class PythonExecutorToolBinding:
    run_script_tool: str
    syntax_check_tool: str
    run_tests_tool: str


class PythonExecutorMCPClient(FilesystemMCPClient):
    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 30.0,
        run_script_tool_name: str | None = None,
        syntax_check_tool_name: str | None = None,
        run_tests_tool_name: str | None = None,
    ) -> None:
        super().__init__(base_url=base_url, timeout_seconds=timeout_seconds)
        self._exec_binding = PythonExecutorToolBinding(
            run_script_tool=run_script_tool_name
            or os.getenv("MCP_PYTHON_RUN_SCRIPT_TOOL", "python_run_script"),
            syntax_check_tool=syntax_check_tool_name
            or os.getenv("MCP_PYTHON_SYNTAX_CHECK_TOOL", "python_syntax_check"),
            run_tests_tool=run_tests_tool_name
            or os.getenv("MCP_PYTHON_RUN_TESTS_TOOL", "python_run_tests"),
        )

    def discover_tools(self) -> PythonExecutorToolBinding:
        logger.info("python_executor:tool_discovery_start")
        response = self._rpc("tools/list")
        tools = response.get("tools", [])
        names = {tool.get("name") for tool in tools if isinstance(tool, dict)}

        run_script_tool = self._exec_binding.run_script_tool
        if run_script_tool not in names:
            run_script_tool = self._find_candidate(
                names,
                ["python_run_script", "execute_python", "python_exec", "run_python", "execute"],
            )

        syntax_check_tool = self._exec_binding.syntax_check_tool
        if syntax_check_tool not in names:
            syntax_check_tool = self._find_candidate(
                names,
                ["python_syntax_check", "syntax_check", "python_check_syntax"],
            )

        run_tests_tool = self._exec_binding.run_tests_tool
        if run_tests_tool not in names:
            run_tests_tool = self._find_candidate(
                names,
                ["python_run_tests", "run_tests", "pytest", "python_pytest"],
            )

        if not run_script_tool or not syntax_check_tool or not run_tests_tool:
            raise MCPClientError(
                f"Unable to bind python executor tools. Available: {sorted(names)}"
            )

        self._exec_binding = PythonExecutorToolBinding(
            run_script_tool=run_script_tool,
            syntax_check_tool=syntax_check_tool,
            run_tests_tool=run_tests_tool,
        )
        logger.info(
            "python_executor:tool_binding_success run_script_tool=%s syntax_check_tool=%s run_tests_tool=%s",
            run_script_tool,
            syntax_check_tool,
            run_tests_tool,
        )
        return self._exec_binding

    def execute_python(self, code: str) -> dict[str, Any]:
        logger.info("python_executor:execute_python_start size=%s", len(code))
        return self._call_tool(self._exec_binding.run_script_tool, {"code": code})

    def syntax_check(self, paths: list[str]) -> dict[str, Any]:
        logger.info("python_executor:syntax_check_start file_count=%s", len(paths))
        return self._call_tool(self._exec_binding.syntax_check_tool, {"paths": paths})

    def run_tests(self, command: str = "python -m pytest -q") -> dict[str, Any]:
        logger.info("python_executor:run_tests_start command=%s", command)
        return self._call_tool(self._exec_binding.run_tests_tool, {"command": command})

    def _call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = self._rpc(
            "tools/call",
            {
                "name": tool_name,
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
