from __future__ import annotations

import logging

from app.graph.state import WorkflowState
from app.mcp.filesystem_client import FilesystemMCPClient
from app.validators import validate_artifact

logger = logging.getLogger(__name__)


def validator_node(state: WorkflowState, fs_client: FilesystemMCPClient) -> WorkflowState:
    logger.info("validator_node_start attempt=%s path=%s", state["attempt_count"], state["artifact_path"])
    content = fs_client.read_file(state["artifact_path"])
    errors = validate_artifact(state["artifact_path"], state["artifact_type"], content)

    if errors:
        logger.info("validation_failure errors=%s", len(errors))
        return {
            **state,
            "validation_passed": False,
            "validation_errors": errors,
            "revision_feedback": "\n".join(f"- {error}" for error in errors),
            "final_status": "failed" if state["attempt_count"] >= state["max_attempts"] else "pending",
        }

    logger.info("validation_success")
    return {
        **state,
        "validation_passed": True,
        "validation_errors": [],
        "revision_feedback": "",
        "final_status": "success",
    }
