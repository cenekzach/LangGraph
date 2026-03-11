from __future__ import annotations

import logging

from langchain_openai import ChatOpenAI

from app.graph.nodes.common import invoke_text
from app.graph.state import WorkflowState
from app.mcp.filesystem_client import FilesystemMCPClient
from app.prompts.builders import requirements_prompt, shrink

logger = logging.getLogger(__name__)


REQUIREMENTS_PATH = "/workspace/artifacts/requirements.current.md"


def requirements_author_node(
    state: WorkflowState,
    llm: ChatOpenAI,
    fs_client: FilesystemMCPClient,
) -> WorkflowState:
    logger.info("requirements_author:start attempt=%s", state["requirements_attempts"] + 1)
    prompt = requirements_prompt(state["user_request"], state["requirements_feedback"])
    markdown = invoke_text(llm, prompt)
    fs_client.write_file(REQUIREMENTS_PATH, markdown)
    logger.info("requirements_author:wrote path=%s", REQUIREMENTS_PATH)

    return {
        **state,
        "requirements_path": REQUIREMENTS_PATH,
        "requirements_summary": shrink(markdown, 1000),
        "requirements_attempts": state["requirements_attempts"] + 1,
        "requirements_ok": False,
        "final_status": "pending",
    }
