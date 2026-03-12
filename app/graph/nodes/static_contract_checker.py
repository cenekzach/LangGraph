from __future__ import annotations

import ast
import logging
import re
from pathlib import Path

from app.graph.nodes.common import safe_json_dumps
from app.graph.state import WorkflowState
from app.mcp.filesystem_client import FilesystemMCPClient

logger = logging.getLogger(__name__)

CONTRACT_CHECK_SUMMARY_PATH = "/workspace/artifacts/contract_check.summary.json"


def static_contract_checker_node(state: WorkflowState, fs_client: FilesystemMCPClient) -> WorkflowState:
    logger.info("static_contract_checker:start")
    issues: list[str] = []
    checked: list[str] = []

    entrypoint = "game.py"
    if state.get("interface_contract_path"):
        try:
            raw = fs_client.read_file(state["interface_contract_path"])
            if '"entrypoint"' in raw:
                match = re.search(r'"entrypoint"\s*:\s*"([^"]+)"', raw)
                if match:
                    entrypoint = match.group(1)
        except Exception as exc:
            issues.append(f"could not read interface contract: {exc}")

    if entrypoint and not Path(entrypoint).exists():
        issues.append(f"missing required entrypoint {entrypoint}")

    module_symbols: dict[str, set[str]] = {}
    for src in state.get("source_paths", []):
        checked.append(src)
        path = Path(src)
        if not path.exists():
            issues.append(f"missing source file {src}")
            continue
        try:
            tree = ast.parse(path.read_text())
        except Exception as exc:
            issues.append(f"source parse failed {src}: {exc}")
            continue
        symbols = {
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        }
        module_symbols[path.stem] = symbols

    for test_path in state.get("test_paths", []):
        checked.append(test_path)
        p = Path(test_path)
        if not p.exists():
            issues.append(f"missing test file {test_path}")
            continue
        try:
            tree = ast.parse(p.read_text())
        except Exception as exc:
            issues.append(f"test parse failed {test_path}: {exc}")
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                target = node.module.split(".")[0]
                if target not in module_symbols:
                    issues.append(f"test imports nonexistent module {target} in {test_path}")
                    continue
                for alias in node.names:
                    if alias.name != "*" and alias.name not in module_symbols[target]:
                        issues.append(
                            f"missing symbol {alias.name} referenced from {target} in {test_path}"
                        )

    contract_ok = not issues
    failure_summary = "ok" if contract_ok else "; ".join(issues[:8])
    fs_client.write_file(
        CONTRACT_CHECK_SUMMARY_PATH,
        safe_json_dumps(
            {
                "contract_ok": contract_ok,
                "issues": issues[:30],
                "checked_files": checked,
                "failure_summary": failure_summary,
            }
        ),
    )
    logger.info("static_contract_checker:contract_ok=%s issues=%s", contract_ok, len(issues))

    return {
        **state,
        "contract_check_ok": contract_ok,
        "contract_check_summary": failure_summary,
        "latest_failure_summary": "" if contract_ok else failure_summary,
    }
