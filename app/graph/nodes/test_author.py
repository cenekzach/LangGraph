from __future__ import annotations

__test__ = False

import logging

from langchain_openai import ChatOpenAI

from app.graph.nodes.common import invoke_text, safe_json_dumps
from app.graph.state import WorkflowState
from app.mcp.filesystem_client import FilesystemMCPClient
from app.prompts.builders import deterministic_tests_prompt
from app.structured_output.parsers import parse_artifact_blocks, parse_tagged_summary

logger = logging.getLogger(__name__)

TEST_SUMMARY_PATH = "/workspace/artifacts/test.summary.json"


def test_author_node(
    state: WorkflowState,
    llm: ChatOpenAI,
    fs_client: FilesystemMCPClient,
) -> WorkflowState:
    logger.info("test_author:start")
    raw = invoke_text(
        llm,
        deterministic_tests_prompt(
            state["requirements_summary"],
            state["implementation_summary"],
            state["source_paths"],
            state["latest_failure_summary"],
            state.get("interface_contract_summary", ""),
        ),
    )

    generated_tests = parse_artifact_blocks(raw)
    if not generated_tests:
        failure_summary = "Invalid test_author artifact format: expected FILE_PATH + fenced content blocks"
        logger.warning("structured_output:validate test_author artifacts failed")
        fs_client.write_file(
            TEST_SUMMARY_PATH,
            safe_json_dumps(
                {
                    "tests_ok": False,
                    "syntax_ok": False,
                    "failing_tests_count": 1,
                    "failure_summary": failure_summary,
                    "test_paths": state["test_paths"],
                }
            ),
        )
        return {
            **state,
            "tests_ok": False,
            "deterministic_test_summary": failure_summary,
            "latest_failure_summary": failure_summary,
        }

    test_paths: list[str] = []
    for item in generated_tests[:8]:
        fs_client.write_file(item["path"], item["content"])
        test_paths.append(item["path"])
        logger.info("test_author:wrote %s", item["path"])

    return {
        **state,
        "test_paths": test_paths or state["test_paths"],
        "deterministic_test_summary": parse_tagged_summary(raw, "TEST_SUMMARY") or "deterministic tests generated",
        "latest_failure_summary": "",
    }
