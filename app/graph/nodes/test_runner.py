from __future__ import annotations

__test__ = False

import logging
import re

from app.graph.nodes.common import safe_json_dumps
from app.graph.state import WorkflowState
from app.mcp.filesystem_client import FilesystemMCPClient
from app.mcp.python_executor_client import PythonExecutorMCPClient

logger = logging.getLogger(__name__)

TEST_SUMMARY_PATH = "/workspace/artifacts/test.summary.json"


def test_runner_node(
    state: WorkflowState,
    fs_client: FilesystemMCPClient,
    pyexec_client: PythonExecutorMCPClient,
) -> WorkflowState:
    logger.info("test_runner:start")

    syntax_paths = state["source_paths"] + state["test_paths"]
    syntax_result = pyexec_client.syntax_check(syntax_paths)
    syntax_ok = int(syntax_result.get("exit_code", 1)) == 0
    logger.info("test_runner:syntax_ok=%s", syntax_ok)

    pytest_result = pyexec_client.run_tests("python -m pytest -q")
    pytest_exit = int(pytest_result.get("exit_code", 1))
    tests_ok = syntax_ok and pytest_exit == 0
    logger.info("test_runner:pytest exit_code=%s", pytest_exit)

    failing_tests_count = _count_failing_tests(pytest_result.get("stdout", "") + "\n" + pytest_result.get("stderr", ""), pytest_exit)
    failure_summary = ""
    if not syntax_ok:
        failure_summary = _compact(syntax_result.get("stderr") or syntax_result.get("stdout", ""))
    elif pytest_exit != 0:
        failure_summary = _compact(pytest_result.get("stderr") or pytest_result.get("stdout", ""))

    payload = {
        "syntax_ok": syntax_ok,
        "tests_ok": tests_ok,
        "failing_tests_count": failing_tests_count,
        "failure_summary": failure_summary,
        "syntax": syntax_result,
        "tests": pytest_result,
    }
    fs_client.write_file(TEST_SUMMARY_PATH, safe_json_dumps(payload))

    summary = (
        "deterministic checks passed"
        if tests_ok
        else f"deterministic checks failed: {failure_summary or f'{failing_tests_count} failing tests'}"
    )

    return {
        **state,
        "tests_ok": tests_ok,
        "deterministic_test_summary": summary,
        "latest_failure_summary": "" if tests_ok else failure_summary,
    }


def _count_failing_tests(output: str, pytest_exit: int) -> int:
    match = re.search(r"(\d+)\s+failed", output)
    if match:
        return int(match.group(1))
    return 1 if pytest_exit != 0 else 0


def _compact(text: str, limit: int = 700) -> str:
    if not text:
        return "Unknown deterministic test failure"
    text = " ".join(text.strip().split())
    return text[:limit]
