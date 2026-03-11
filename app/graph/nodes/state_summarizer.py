from __future__ import annotations

import logging

from app.graph.state import WorkflowState
from app.mcp.filesystem_client import FilesystemMCPClient

logger = logging.getLogger(__name__)

LOOP_SUMMARY_PATH = "/workspace/artifacts/loop.summary.md"


def state_summarizer_node(state: WorkflowState, fs_client: FilesystemMCPClient) -> WorkflowState:
    summary = (
        f"# Loop summary\n"
        f"- requirements_attempts: {state['requirements_attempts']}\n"
        f"- implementation_attempts: {state['implementation_attempts']}\n"
        f"- review_attempts: {state['review_attempts']}\n"
        f"- latest_failure_summary: {state['latest_failure_summary'][:500]}\n"
    )
    fs_client.write_file(LOOP_SUMMARY_PATH, summary)
    logger.info("state_summarizer:wrote path=%s", LOOP_SUMMARY_PATH)
    return state
