from __future__ import annotations

import json
import logging

from langchain_openai import ChatOpenAI

from app.graph.nodes.common import invoke_json, safe_json_dumps
from app.graph.state import WorkflowState
from app.mcp.filesystem_client import FilesystemMCPClient
from app.prompts.builders import implementation_prompt

logger = logging.getLogger(__name__)

IMPLEMENTATION_SUMMARY_PATH = "/workspace/artifacts/implementation.summary.json"


def _implementation_retry_prompt(base_prompt: str) -> str:
    return (
        f"{base_prompt}\n\n"
        "Return valid JSON only. "
        "Do not include markdown fences, commentary, or prose before/after the JSON."
    )


def implementor_node(
    state: WorkflowState,
    llm: ChatOpenAI,
    fs_client: FilesystemMCPClient,
) -> WorkflowState:
    logger.info("implementor:start attempt=%s", state["implementation_attempts"] + 1)
    base_prompt = implementation_prompt(
        state["user_request"],
        state["requirements_summary"],
        state["latest_failure_summary"],
    )

    try:
        plan = invoke_json(llm, base_prompt)
    except json.JSONDecodeError:
        logger.warning("implementor:invalid_json retrying_with_stricter_prompt=true")
        try:
            plan = invoke_json(llm, _implementation_retry_prompt(base_prompt))
        except json.JSONDecodeError:
            logger.error("implementor:invalid_json fallback_to_empty_plan=true")
            plan = {
                "source_files": [],
                "implementation_summary": "implementation plan unavailable (invalid LLM JSON)",
            }

    source_files = plan.get("source_files", [])
    written_paths: list[str] = []
    for item in source_files[:8]:
        path = item.get("path", "")
        content = item.get("content", "")
        if not path or not isinstance(content, str):
            continue
        fs_client.write_file(path, content)
        written_paths.append(path)
        logger.info("implementor:wrote %s", path)

    summary_payload = {
        "implementation_summary": plan.get("implementation_summary", "implementation updated"),
        "source_paths": written_paths,
    }
    fs_client.write_file(IMPLEMENTATION_SUMMARY_PATH, safe_json_dumps(summary_payload))

    return {
        **state,
        "source_paths": written_paths or state["source_paths"],
        "implementation_summary": summary_payload["implementation_summary"],
        "implementation_attempts": state["implementation_attempts"] + 1,
        "latest_failure_summary": "",
    }
