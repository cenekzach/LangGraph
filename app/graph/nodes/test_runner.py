from __future__ import annotations

__test__ = False

import json
import logging
import re

from app.graph.nodes.common import safe_json_dumps
from app.graph.state import WorkflowState
from app.mcp.filesystem_client import FilesystemMCPClient
from app.mcp.python_executor_client import PythonExecutorMCPClient

logger = logging.getLogger(__name__)

TEST_SUMMARY_PATH = "/workspace/artifacts/test.summary.json"
TEST_DETAIL_PATH = "/workspace/artifacts/test.details.json"


def test_runner_node(
    state: WorkflowState,
    fs_client: FilesystemMCPClient,
    pyexec_client: PythonExecutorMCPClient,
) -> WorkflowState:
    logger.info("test_runner:start")

    syntax_paths = [p for p in (state.get("source_paths", []) + state.get("test_paths", [])) if p.endswith(".py")]
    syntax_checks = [pyexec_client.python_syntax_check(path) for path in syntax_paths]
    syntax_ok = bool(syntax_checks) and all(check.get("ok") and check.get("valid") for check in syntax_checks)
    failing_files = [c.get("path") for c in syntax_checks if not c.get("valid")]
    logger.info("test_runner:syntax_ok=%s checked=%s", syntax_ok, len(syntax_checks))

    pytest_result = pyexec_client.python_run_tests("python -m pytest -q")
    pytest_ok = bool(pytest_result.get("ok")) and pytest_result.get("exit_code") == 0
    pytest_exit = pytest_result.get("exit_code")
    logger.info("test_runner:pytest exit_code=%s tests_ok=%s", pytest_exit, pytest_ok)

    scenario_result = _run_cli_contract_scenario(state, pyexec_client)
    scenario_ok = scenario_result["scenario_ok"]

    tests_ok = syntax_ok and pytest_ok and scenario_ok
    combined_output = (
        (pytest_result.get("stdout", "") or "") + "\n" + (pytest_result.get("stderr", "") or "")
    )
    failing_tests_count = _count_failing_tests(combined_output, pytest_exit if isinstance(pytest_exit, int) else 1)

    if not syntax_ok:
        failure_summary = f"syntax checks failed for: {', '.join(str(x) for x in failing_files[:5])}"
    elif not pytest_ok:
        failure_summary = _compact(pytest_result.get("stderr") or pytest_result.get("stdout") or "pytest failed")
    elif not scenario_ok:
        failure_summary = scenario_result["failure_summary"]
    else:
        failure_summary = ""

    summary_payload = {
        "syntax_ok": syntax_ok,
        "pytest_ok": pytest_ok,
        "scenario_ok": scenario_ok,
        "tests_ok": tests_ok,
        "pytest_exit_code": pytest_exit,
        "failing_files": failing_files,
        "failing_tests_count": failing_tests_count,
        "failure_summary": failure_summary,
        "detailed_report_path": TEST_DETAIL_PATH,
    }
    detail_payload = {
        "syntax_checks": syntax_checks,
        "pytest": pytest_result,
        "scenario": scenario_result,
    }
    fs_client.write_file(TEST_SUMMARY_PATH, safe_json_dumps(summary_payload))
    fs_client.write_file(TEST_DETAIL_PATH, safe_json_dumps(detail_payload))

    return {
        **state,
        "syntax_ok": syntax_ok,
        "pytest_ok": pytest_ok,
        "scenario_ok": scenario_ok,
        "tests_ok": tests_ok,
        "test_summary": json.dumps(summary_payload, ensure_ascii=False),
        "deterministic_test_summary": "deterministic checks passed" if tests_ok else failure_summary,
        "latest_failure_summary": "" if tests_ok else failure_summary,
    }


def _run_cli_contract_scenario(state: WorkflowState, pyexec_client: PythonExecutorMCPClient) -> dict[str, object]:
    target = _pick_target_script(state.get("source_paths", []))
    if not target:
        return {"scenario_ok": True, "failure_summary": "no CLI target discovered", "checks": []}

    checks: list[dict[str, object]] = []

    first = pyexec_client.python_run_script(f"python {target} --exit", as_command=True)
    check_exit = bool(first.get("ok")) and first.get("exit_code") == 0
    checks.append({"name": "exit_flag", "ok": check_exit})
    if not check_exit:
        return {"scenario_ok": False, "failure_summary": "--exit contract check failed", "checks": checks}

    replay = pyexec_client.python_run_script(f"python {target} --actions 1,1 --exit", as_command=True)
    replay2 = pyexec_client.python_run_script(f"python {target} --actions 1,1 --exit", as_command=True)
    deterministic_ok = (
        bool(replay.get("ok"))
        and bool(replay2.get("ok"))
        and replay.get("exit_code") == 0
        and replay2.get("exit_code") == 0
        and (replay.get("stdout", "") == replay2.get("stdout", ""))
    )
    checks.append({"name": "deterministic_replay", "ok": deterministic_ok})
    if not deterministic_ok:
        return {"scenario_ok": False, "failure_summary": "deterministic replay failed for --actions", "checks": checks}

    return {"scenario_ok": True, "failure_summary": "", "checks": checks}


def _pick_target_script(paths: list[str]) -> str | None:
    for preferred in ("game.py", "main.py", "app.py"):
        for path in paths:
            if path.endswith(preferred):
                return path
    for path in paths:
        if path.endswith(".py"):
            return path
    return None


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
