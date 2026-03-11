from __future__ import annotations

import logging

from langchain_openai import ChatOpenAI

from app.graph.nodes.common import invoke_json
from app.graph.state import WorkflowState
from app.mcp.filesystem_client import FilesystemMCPClient
from app.prompts.builders import requirements_review_prompt

logger = logging.getLogger(__name__)


def requirements_reviewer_node(
    state: WorkflowState,
    llm: ChatOpenAI,
    fs_client: FilesystemMCPClient,
) -> WorkflowState:
    logger.info("requirements_reviewer:start")
    requirements_md = fs_client.read_file(state["requirements_path"])
    review = invoke_json(llm, requirements_review_prompt(requirements_md))
    ok = bool(review.get("requirements_ok", False))
    issues = review.get("issues", [])
    feedback = review.get("rewrite_instructions", "")
    summary = review.get("summary", "requirements reviewed")

    logger.info("requirements_reviewer:%s issues=%s", "pass" if ok else "fail", len(issues))
    return {
        **state,
        "requirements_ok": ok,
        "requirements_feedback": feedback if not ok else "",
        "requirements_summary": summary,
        "latest_failure_summary": "; ".join(issues[:5]) if issues else "",
    }
