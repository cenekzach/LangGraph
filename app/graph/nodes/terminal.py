from __future__ import annotations

import logging

from app.graph.nodes.common import safe_json_dumps
from app.graph.state import WorkflowState
from app.mcp.filesystem_client import FilesystemMCPClient

logger = logging.getLogger(__name__)

FINAL_STATUS_PATH = "/workspace/artifacts/final_status.json"


def terminal_node(state: WorkflowState, fs_client: FilesystemMCPClient) -> WorkflowState:
    payload = {
        "final_status": state.get("final_status", "failed_internal_error"),
        "failure_category": state.get("failure_category", ""),
        "last_route_reason": state.get("last_route_reason", ""),
        "latest_failure_summary": state.get("latest_failure_summary", ""),
        "attempt_counts": state.get("attempt_counts", {}),
        "suggested_next_intervention": _suggest(state),
    }
    fs_client.write_file(FINAL_STATUS_PATH, safe_json_dumps(payload))
    logger.info("workflow:end %s", payload["final_status"])
    return state


def _suggest(state: WorkflowState) -> str:
    mapping = {
        "failed_requirements": "change_planner",
        "failed_implementation": "implementor",
        "failed_tests": "implementor",
        "failed_playtest": "implementor",
        "failed_review": "change_planner",
        "failed_internal_error": "last_failed_node",
    }
    return mapping.get(state.get("final_status", ""), "none")
