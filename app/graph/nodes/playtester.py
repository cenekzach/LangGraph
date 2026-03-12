from __future__ import annotations

import json
import logging
import re

from langchain_openai import ChatOpenAI

from app.graph.nodes.common import invoke_text, safe_json_dumps
from app.graph.state import WorkflowState
from app.mcp.filesystem_client import FilesystemMCPClient
from app.mcp.python_executor_client import PythonExecutorMCPClient
from app.prompts.builders import playtester_prompt

logger = logging.getLogger(__name__)

PLAYTEST_SUMMARY_PATH = "/workspace/artifacts/playtest.summary.json"
PLAYTEST_LOG_PATH = "/workspace/artifacts/playtest.log.md"


def playtester_node(
    state: WorkflowState,
    llm: ChatOpenAI,
    fs_client: FilesystemMCPClient,
    pyexec_client: PythonExecutorMCPClient,
) -> WorkflowState:
    logger.info("playtester:start attempt=%s", state["playtest_attempts"] + 1)
    target = _pick_target_script(state["source_paths"])
    if not target:
        summary = "No runnable game script found for playtester"
        return _fail(state, fs_client, summary, [])

    actions: list[int] = []
    visited = set()
    log_lines = [f"# Playtest log for {target}"]
    max_steps = 15

    for step in range(1, max_steps + 1):
        seq = ",".join(str(a) for a in actions)
        cmd = f"python {target} --actions {seq} --exit" if seq else f"python {target} --exit"
        result = pyexec_client.run_tests(cmd)
        output = (result.get("stdout", "") + "\n" + result.get("stderr", "")).strip()
        logger.info("playtester:step=%s actions=%s", step, seq or "<none>")
        log_lines.append(f"## Step {step}\n- actions: {seq or '<none>'}\n- exit_code: {result.get('exit_code', 1)}\n")

        if int(result.get("exit_code", 1)) != 0:
            return _fail(state, fs_client, f"playtest execution failed at step {step}", actions, log_lines)

        key = (tuple(actions), _compact(output, 350))
        if key in visited:
            return _fail(state, fs_client, "repeated state with no progress", actions, log_lines)
        visited.add(key)

        if _is_win(output):
            summary = {
                "playtest_ok": True,
                "won_game": True,
                "actions_attempted": actions,
                "steps_taken": step,
                "failure_reason": None,
                "bug_report": "",
            }
            fs_client.write_file(PLAYTEST_SUMMARY_PATH, safe_json_dumps(summary))
            fs_client.write_file(PLAYTEST_LOG_PATH, "\n".join(log_lines))
            return {
                **state,
                "playtest_ok": True,
                "playtest_summary": "playtester reached a winning state",
                "play_actions_attempted": actions,
                "playtest_attempts": state["playtest_attempts"] + 1,
                "latest_failure_summary": "",
            }

        available = _extract_actions(output)
        if not available:
            return _fail(state, fs_client, "no numeric actions detected in output", actions, log_lines)

        next_action = _choose_next_action(llm, state["requirements_summary"], actions, output, available)
        if next_action not in available:
            next_action = available[0]

        actions.append(next_action)

    return _fail(state, fs_client, "step limit reached before winning", actions, log_lines)


def _choose_next_action(llm: ChatOpenAI, req: str, actions: list[int], output: str, available: list[int]) -> int:
    raw = invoke_text(
        llm,
        playtester_prompt(req, f"actions_so_far={actions}; available={available}", output),
    )
    try:
        choice = json.loads(raw.strip())
        value = int(choice.get("next_action"))
        return value
    except Exception:
        for action in available:
            if action not in actions:
                return action
        return available[0]


def _pick_target_script(paths: list[str]) -> str | None:
    for preferred in ("game.py", "main.py", "app.py"):
        for path in paths:
            if path.endswith(preferred):
                return path
    for path in paths:
        if path.endswith(".py"):
            return path
    return None


def _extract_actions(output: str) -> list[int]:
    found = {int(n) for n in re.findall(r"(?:^|\n|\s)(\d+)\s*[\).:-]", output)}
    return sorted(found)


def _is_win(output: str) -> bool:
    lower = output.lower()
    return any(token in lower for token in ["you win", "victory", "won the game", "success!"])


def _compact(text: str, limit: int = 240) -> str:
    return " ".join((text or "").split())[:limit]


def _fail(
    state: WorkflowState,
    fs_client: FilesystemMCPClient,
    reason: str,
    actions: list[int],
    log_lines: list[str] | None = None,
) -> WorkflowState:
    summary = {
        "playtest_ok": False,
        "won_game": False,
        "actions_attempted": actions,
        "steps_taken": len(actions),
        "failure_reason": reason,
        "bug_report": reason,
    }
    fs_client.write_file(PLAYTEST_SUMMARY_PATH, safe_json_dumps(summary))
    if log_lines:
        fs_client.write_file(PLAYTEST_LOG_PATH, "\n".join(log_lines))
    return {
        **state,
        "playtest_ok": False,
        "playtest_summary": reason,
        "play_actions_attempted": actions,
        "playtest_attempts": state["playtest_attempts"] + 1,
        "latest_failure_summary": reason,
    }
