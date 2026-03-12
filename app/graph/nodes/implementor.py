from __future__ import annotations

import logging

from langchain_openai import ChatOpenAI

from app.graph.nodes.common import invoke_text, safe_json_dumps
from app.graph.state import WorkflowState
from app.mcp.filesystem_client import FilesystemMCPClient
from app.prompts.builders import implementation_prompt
from app.structured_output.parsers import parse_artifact_blocks, parse_tagged_summary

logger = logging.getLogger(__name__)

IMPLEMENTATION_SUMMARY_PATH = "/workspace/artifacts/implementation.summary.json"


def implementor_node(
    state: WorkflowState,
    llm: ChatOpenAI,
    fs_client: FilesystemMCPClient,
) -> WorkflowState:
    logger.info("implementor:start attempt=%s", state["implementation_attempts"] + 1)
    prompt = implementation_prompt(
        state["user_request"],
        state["requirements_summary"],
        state["latest_failure_summary"],
        state.get("change_scope", ""),
    )
    raw = invoke_text(llm, prompt)

    source_files = parse_artifact_blocks(raw)
    if not source_files:
        msg = "Invalid implementor artifact format: expected FILE_PATH + fenced content blocks"
        logger.warning("structured_output:validate implementor artifacts failed")
        logger.info("router:implementor -> implementor due to invalid metadata")
        fs_client.write_file(
            IMPLEMENTATION_SUMMARY_PATH,
            safe_json_dumps({"implementation_summary": msg, "source_paths": state["source_paths"]}),
        )
        return {
            **state,
            "implementation_attempts": state["implementation_attempts"] + 1,
            "latest_failure_summary": msg,
            "implementation_summary": msg,
        }

    written_paths: list[str] = []
    for item in source_files[:8]:
        fs_client.write_file(item["path"], item["content"])
        written_paths.append(item["path"])
        logger.info("implementor:wrote %s", item["path"])

    summary_payload = {
        "implementation_summary": parse_tagged_summary(raw, "IMPLEMENTATION_SUMMARY")
        or "implementation updated",
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
