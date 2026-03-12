from __future__ import annotations

import logging
import os
import time
import json
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

    def python_syntax_check(self, path: str) -> dict[str, Any]:
        logger.info("python_executor:syntax_check_start path=%s", path)
        started = time.perf_counter()
        try:
            normalized = self._call_tool(self._exec_binding.syntax_check_tool, {"path": path})
            content = normalized.get("content", {})
            valid = bool(content.get("valid", normalized.get("exit_code", 1) == 0))
            return {
                "ok": True,
                "valid": valid,
                "path": str(content.get("path") or path),
                "error_type": content.get("error_type"),
                "error_message": content.get("error_message"),
                "line": content.get("line"),
                "offset": content.get("offset"),
                "duration_ms": int((time.perf_counter() - started) * 1000),
            }
        except Exception as exc:
            logger.exception("python_executor:syntax_check_transport_error path=%s", path)
            return {
                "ok": False,
                "valid": False,
                "path": path,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "line": None,
                "offset": None,
                "duration_ms": int((time.perf_counter() - started) * 1000),
            }

    def python_run_tests(self, command: str = "python -m pytest -q -p no:cacheprovider tests") -> dict[str, Any]:
        logger.info("python_executor:run_tests_start command=%s", command)
        return self._run_command_tool(self._exec_binding.run_tests_tool, {"command": command})

    def python_run_script(
        self,
        path: str,
        args: list[str] | None = None,
        *,
        stdin_text: str = "",
        timeout_seconds: int = 30,
        cwd: str = ".",
    ) -> dict[str, Any]:
        logger.info("python_executor:run_script_start path=%s args=%s", path, args or [])
        payload = {
            "path": path,
            "args": args or [],
            "stdin_text": stdin_text,
            "timeout_seconds": timeout_seconds,
            "cwd": cwd,
        }
        return self._run_command_tool(self._exec_binding.run_script_tool, payload)

    # Backward compatibility
    def execute_python(self, code: str) -> dict[str, Any]:
        return self.python_run_script(path="-c", args=[code])

    def syntax_check(self, paths: list[str]) -> dict[str, Any]:
        checks = [self.python_syntax_check(path) for path in paths]
        return {
            "ok": all(item.get("ok", False) for item in checks),
            "checks": checks,
            "exit_code": 0 if checks and all(item.get("valid", False) for item in checks) else 1,
            "stdout": "",
            "stderr": "\n".join(
                f"{item.get('path')}: {item.get('error_type')}: {item.get('error_message')}"
                for item in checks
                if not item.get("valid", False)
            ).strip(),
        }

    def run_tests(self, command: str = "python -m pytest -q -p no:cacheprovider tests") -> dict[str, Any]:
        return self.python_run_tests(command)

    def _run_command_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            normalized = self._call_tool(tool_name, arguments)
            content = self._extract_command_content(normalized)
            exit_code = self._as_int(content.get("exit_code", normalized.get("exit_code")))
            timed_out = bool(content.get("timed_out", False))
            return {
                "ok": True,
                "exit_code": exit_code,
                "stdout": str(content.get("stdout", normalized.get("stdout", ""))),
                "stderr": str(content.get("stderr", normalized.get("stderr", ""))),
                "timed_out": timed_out,
                "duration_ms": int((time.perf_counter() - started) * 1000),
            }
        except Exception as exc:
            logger.exception("python_executor:command_transport_error tool=%s", tool_name)
            return {
                "ok": False,
                "exit_code": None,
                "stdout": "",
                "stderr": str(exc),
                "timed_out": False,
                "duration_ms": int((time.perf_counter() - started) * 1000),
            }

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
    def _as_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _normalize_result(result: dict[str, Any]) -> dict[str, Any]:
        if isinstance(result.get("structuredContent"), dict):
            content = result["structuredContent"]
            return {
                "stdout": str(content.get("stdout", "")),
                "stderr": str(content.get("stderr", "")),
                "exit_code": content.get("exit_code", 0),
                "content": content,
            }
        text = FilesystemMCPClient._extract_content(result)
        return {"stdout": text, "stderr": "", "exit_code": 0, "content": {"stdout": text, "stderr": "", "exit_code": 0}}

    @staticmethod
    def _extract_command_content(normalized: dict[str, Any]) -> dict[str, Any]:
        content = normalized.get("content", {})
        if not isinstance(content, dict):
            content = {}

        parsed = PythonExecutorMCPClient._extract_embedded_payload(normalized.get("stdout", ""))
        if parsed is not None:
            merged = dict(content)
            merged.update(parsed)
            return merged
        return content

    @staticmethod
    def _extract_embedded_payload(text: str) -> dict[str, Any] | None:
        stripped = (text or "").strip()
        if not stripped:
            return None

        candidates = [stripped]
        for line in reversed(stripped.splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                candidates.append(line)

        for candidate in candidates:
            try:
                decoded = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(decoded, dict) and "exit_code" in decoded:
                return decoded
        return None
