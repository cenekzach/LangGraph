from __future__ import annotations

import json
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

    syntax_script = _syntax_script(state["source_paths"] + test_paths)
    syntax_result = pyexec_client.execute_python(syntax_script)
    syntax_ok = int(syntax_result.get("exit_code", 1)) == 0
    logger.info("tester:syntax %s", "ok" if syntax_ok else "failed")

    test_cmd = "python -m pytest -q" if test_paths else "python -m pytest -q"
    test_result = pyexec_client.execute_command(test_cmd)
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


def _syntax_script(paths: list[str]) -> str:
    quoted = json.dumps(paths)
    return f"""
import ast
from pathlib import Path
paths = {quoted}
for path in paths:
    p = Path(path)
    if p.suffix != '.py' or not p.exists():
        continue
    ast.parse(p.read_text())
print('syntax ok')
""".strip()


def _compact(text: str, limit: int = 700) -> str:
    if not text:
        return "Unknown test failure"
    text = " ".join(text.strip().split())
    return text[:limit]
