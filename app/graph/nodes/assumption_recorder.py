from __future__ import annotations

import logging

from app.graph.state import WorkflowState
from app.mcp.filesystem_client import FilesystemMCPClient

logger = logging.getLogger(__name__)

ASSUMPTIONS_PATH = "/workspace/artifacts/requirements.assumptions.md"


def assumption_recorder_node(state: WorkflowState, fs_client: FilesystemMCPClient) -> WorkflowState:
    assumptions = [a.strip() for a in state.get("assumptions_to_record", []) if a.strip()]
    unique = list(dict.fromkeys(assumptions))

    lines = ["# Requirements Assumptions", "", "Recorded non-blocking assumptions used for implementation.", ""]
    if unique:
        lines.extend([f"- {item}" for item in unique])
    else:
        lines.append("- None")
    content = "\n".join(lines) + "\n"

    fs_client.write_file(ASSUMPTIONS_PATH, content)
    logger.info("assumption_recorder:wrote %s assumptions", len(unique))

    return {**state, "assumptions_to_record": unique}
