from __future__ import annotations

import itertools
import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class MCPClientError(RuntimeError):
    pass


@dataclass
class FilesystemToolBinding:
    read_tool: str
    write_tool: str


class FilesystemMCPClient:
    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 20.0,
        read_tool_name: str | None = None,
        write_tool_name: str | None = None,
        workspace_prefix: str = "",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.workspace_prefix = workspace_prefix.strip()
        self._client = httpx.Client(timeout=self.timeout_seconds)
        self._ids = itertools.count(1)
        self._binding = FilesystemToolBinding(
            read_tool=read_tool_name or os.getenv("MCP_FS_READ_TOOL", "read_file"),
            write_tool=write_tool_name or os.getenv("MCP_FS_WRITE_TOOL", "write_file"),
        )

    def connect(self) -> None:
        logger.info("mcp_connect_attempt base_url=%s", self.base_url)
        try:
            self._rpc(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "clientInfo": {"name": "langgraph-devops-poc", "version": "0.2.0"},
                    "capabilities": {},
                },
            )
        except MCPClientError:
            # Some servers allow tool calls without explicit initialization.
            logger.warning("mcp_initialize_failed continuing_without_initialize=true")

    def discover_tools(self) -> FilesystemToolBinding:
        logger.info("mcp_tool_discovery_start")
        response = self._rpc("tools/list", {})
        tools = response.get("tools", [])
        names = {tool.get("name") for tool in tools if isinstance(tool, dict)}

        read_tool = self._binding.read_tool
        write_tool = self._binding.write_tool

        if read_tool not in names:
            read_tool = self._find_candidate(names, ["read_file", "filesystem_read", "read"])
        if write_tool not in names:
            write_tool = self._find_candidate(names, ["write_file", "filesystem_write", "write"])

        if not read_tool or not write_tool:
            raise MCPClientError(
                f"Unable to bind filesystem tools. Available tools: {sorted(names)}"
            )

        self._binding = FilesystemToolBinding(read_tool=read_tool, write_tool=write_tool)
        logger.info(
            "mcp_tool_binding_success read_tool=%s write_tool=%s",
            self._binding.read_tool,
            self._binding.write_tool,
        )
        return self._binding

    def write_file(self, path: str, content: str) -> None:
        full_path = self._normalize_path(path)
        logger.info("filesystem_write_attempt path=%s", full_path)
        result = self._rpc(
            "tools/call",
            {
                "name": self._binding.write_tool,
                "arguments": {"path": full_path, "content": content},
            },
        )
        if result.get("isError"):
            raise MCPClientError(f"Filesystem write failed: {result}")
        logger.info("filesystem_write_success path=%s", full_path)

    def read_file(self, path: str) -> str:
        full_path = self._normalize_path(path)
        logger.info("filesystem_read_attempt path=%s", full_path)
        result = self._rpc(
            "tools/call",
            {
                "name": self._binding.read_tool,
                "arguments": {"path": full_path},
            },
        )
        if result.get("isError"):
            raise MCPClientError(f"Filesystem read failed: {result}")

        content = self._extract_content(result)
        logger.info("filesystem_read_success path=%s size=%s", full_path, len(content))
        return content

    def _normalize_path(self, path: str) -> str:
        if self.workspace_prefix:
            return f"{self.workspace_prefix.rstrip('/')}/{path.lstrip('/')}"
        return path

    def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": next(self._ids),
            "method": method,
            "params": params,
        }
        try:
            response = self._client.post(self.base_url, json=payload)
            response.raise_for_status()
            body = response.json()
        except Exception as exc:
            raise MCPClientError(f"MCP request failed for method '{method}': {exc}") from exc

        if "error" in body:
            raise MCPClientError(f"MCP error for method '{method}': {body['error']}")
        if "result" not in body:
            raise MCPClientError(f"MCP malformed response for method '{method}': {body}")
        return body["result"]

    @staticmethod
    def _find_candidate(names: set[str], candidates: list[str]) -> str | None:
        for candidate in candidates:
            if candidate in names:
                return candidate
        return None

    @staticmethod
    def _extract_content(result: dict[str, Any]) -> str:
        content = result.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_chunks = [chunk.get("text", "") for chunk in content if isinstance(chunk, dict)]
            if text_chunks:
                return "\n".join(text_chunks)
        if isinstance(result.get("text"), str):
            return result["text"]
        raise MCPClientError(f"Unable to extract file content from MCP response: {result}")
