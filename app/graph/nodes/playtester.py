from __future__ import annotations

import hashlib
import logging
import re
from collections import deque

from langchain_openai import ChatOpenAI

from app.graph.nodes.common import safe_json_dumps
from app.graph.state import WorkflowState
from app.mcp.filesystem_client import FilesystemMCPClient
from app.mcp.python_executor_client import PythonExecutorMCPClient

logger = logging.getLogger(__name__)

PLAYTEST_SUMMARY_PATH = "/workspace/artifacts/playtest.summary.json"
PLAYTEST_LOG_PATH = "/workspace/artifacts/playtest.log.md"


def playtester_node(
    state: WorkflowState,
    _llm: ChatOpenAI,
    fs_client: FilesystemMCPClient,
    pyexec_client: PythonExecutorMCPClient,
) -> WorkflowState:
    logger.info("playtester:start attempt=%s", state["playtest_attempts"] + 1)
    target = _pick_target_script(state["source_paths"])
    if not target:
        return _fail(state, fs_client, "could not identify runnable entrypoint", [], 0, 0, [])

    max_expansions = 30
    frontier = deque([[]])
    seen_hashes: set[str] = set()
    log_lines = [f"# Playtest log for {target}"]
    expansions = 0

    while frontier and expansions < max_expansions:
        actions = frontier.popleft()
        expansions += 1
        result = _run_sequence(target, actions, pyexec_client)
        output = (result.get("stdout", "") + "\n" + result.get("stderr", "")).strip()
        state_hash = _hash_state(output)
        logger.info("playtester:expansion=%s actions=%s", expansions, actions)
        log_lines.append(f"- expansion={expansions} actions={actions} exit={result.get('exit_code')}")

        if not result.get("ok") or result.get("exit_code") != 0:
            return _fail(state, fs_client, "playtest execution failed", actions, expansions, len(seen_hashes), log_lines)

        if _is_win(output):
            summary = {
                "playtest_ok": True,
                "won_game": True,
                "actions_attempted": actions,
                "steps_taken": len(actions),
                "visited_states_count": len(seen_hashes) + 1,
                "failure_reason": None,
                "bug_report": "",
                "play_log_path": PLAYTEST_LOG_PATH,
            }
            fs_client.write_file(PLAYTEST_SUMMARY_PATH, safe_json_dumps(summary))
            fs_client.write_file(PLAYTEST_LOG_PATH, "\n".join(log_lines))
            return {
                **state,
                "playtest_ok": True,
                "playtest_summary": "playtester reached a winning state",
                "play_actions_attempted": actions,
                "playtest_attempts": state["playtest_attempts"] + 1,
                "attempt_counts": {**state.get("attempt_counts", {}), "playtest": state["playtest_attempts"] + 1},
                "latest_failure_summary": "",
            }

        if state_hash in seen_hashes:
            logger.info("playtester:state_repeat detected after actions=%s", ",".join(str(a) for a in actions))
            continue
        seen_hashes.add(state_hash)

        available = _extract_actions(output)
        if not available:
            return _fail(
                state,
                fs_client,
                "could not parse available actions",
                actions,
                expansions,
                len(seen_hashes),
                log_lines,
            )

        for action in available:
            frontier.append(actions + [action])

    reason = "frontier exhausted without winning" if not frontier else "expansion limit reached before winning"
    return _fail(state, fs_client, reason, [], expansions, len(seen_hashes), log_lines)


def _run_sequence(target: str, actions: list[int], pyexec_client: PythonExecutorMCPClient) -> dict:
    seq = ",".join(str(a) for a in actions)
    command = f"python {target} --actions {seq} --exit" if seq else f"python {target} --exit"
    return pyexec_client.python_run_script(command, as_command=True)


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


def _normalize_state(text: str) -> str:
    lines = [" ".join(line.split()) for line in (text or "").splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def _hash_state(text: str) -> str:
    normalized = _normalize_state(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _is_win(output: str) -> bool:
    lower = output.lower()
    return any(token in lower for token in ["you win", "victory", "won the game", "success!", "you escaped", "door unlocks"])


def _fail(
    state: WorkflowState,
    fs_client: FilesystemMCPClient,
    reason: str,
    actions: list[int],
    expansions: int,
    visited_states_count: int,
    log_lines: list[str] | None = None,
) -> WorkflowState:
    summary = {
        "playtest_ok": False,
        "won_game": False,
        "actions_attempted": actions,
        "steps_taken": len(actions),
        "visited_states_count": visited_states_count,
        "failure_reason": reason,
        "bug_report": reason,
        "play_log_path": PLAYTEST_LOG_PATH,
    }
    fs_client.write_file(PLAYTEST_SUMMARY_PATH, safe_json_dumps(summary))
    if log_lines:
        fs_client.write_file(PLAYTEST_LOG_PATH, "\n".join(log_lines))
    logger.info("playtester:failed reason=%s expansions=%s visited=%s", reason, expansions, visited_states_count)
    return {
        **state,
        "playtest_ok": False,
        "playtest_summary": reason,
        "play_actions_attempted": actions,
        "playtest_attempts": state["playtest_attempts"] + 1,
        "attempt_counts": {**state.get("attempt_counts", {}), "playtest": state["playtest_attempts"] + 1},
        "latest_failure_summary": reason,
    }
