from __future__ import annotations

import logging

from langchain_openai import ChatOpenAI

from app.graph.nodes.common import invoke_json, safe_json_dumps
from app.graph.state import WorkflowState
from app.mcp.filesystem_client import FilesystemMCPClient
from app.mcp.python_executor_client import PythonExecutorMCPClient
from app.prompts.builders import tests_prompt

logger = logging.getLogger(__name__)

TEST_SUMMARY_PATH = "/workspace/artifacts/test.summary.json"


def tester_node(
    state: WorkflowState,
    llm: ChatOpenAI,
    fs_client: FilesystemMCPClient,
    pyexec_client: PythonExecutorMCPClient,
) -> WorkflowState:
    logger.info("tester:start")
    generated = invoke_json(
        llm,
        tests_prompt(
            state["requirements_summary"],
            state["implementation_summary"],
            state["source_paths"],
        ),
    )

    test_paths: list[str] = []
    for item in generated.get("test_files", [])[:8]:
        path = item.get("path", "")
        content = item.get("content", "")
        if not path or not isinstance(content, str):
            continue
        fs_client.write_file(path, content)
        test_paths.append(path)
        logger.info("tester:wrote %s", path)

    syntax_paths = state["source_paths"] + test_paths
    syntax_result = pyexec_client.syntax_check(syntax_paths)
    syntax_ok = int(syntax_result.get("exit_code", 1)) == 0
    logger.info("tester:syntax %s", "ok" if syntax_ok else "failed")

    test_result = pyexec_client.run_tests("python -m pytest -q")
    tests_ok = syntax_ok and int(test_result.get("exit_code", 1)) == 0
    logger.info("tester:pytest %s", "passed" if tests_ok else "failed")

    failure_summary = ""
    if not syntax_ok:
        failure_summary = _compact(syntax_result.get("stderr") or syntax_result.get("stdout", ""))
    elif not tests_ok:
        failure_summary = _compact(test_result.get("stderr") or test_result.get("stdout", ""))

    payload = {
        "tests_ok": tests_ok,
        "test_summary": generated.get("test_summary", "tests generated and executed"),
        "syntax": syntax_result,
        "tests": test_result,
        "failure_summary": failure_summary,
        "test_paths": test_paths,
    }
    fs_client.write_file(TEST_SUMMARY_PATH, safe_json_dumps(payload))

    return {
        **state,
        "test_paths": test_paths or state["test_paths"],
        "tests_ok": tests_ok,
        "test_summary": payload["test_summary"],
        "latest_failure_summary": failure_summary,
    }


def _compact(text: str, limit: int = 700) -> str:
    if not text:
        return "Unknown test failure"
    text = " ".join(text.strip().split())
    return text[:limit]
