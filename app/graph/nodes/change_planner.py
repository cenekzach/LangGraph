from __future__ import annotations

import logging

from langchain_openai import ChatOpenAI

from app.graph.nodes.common import invoke_text, safe_json_dumps
from app.graph.state import WorkflowState
from app.mcp.filesystem_client import FilesystemMCPClient
from app.prompts.builders import change_planner_prompt, parse_change_scope

logger = logging.getLogger(__name__)

REQUIREMENTS_PATH = "/workspace/artifacts/requirements.current.md"
CHANGE_SCOPE_PATH = "/workspace/artifacts/change_scope.json"


def change_planner_node(
    state: WorkflowState,
    llm: ChatOpenAI,
    fs_client: FilesystemMCPClient,
) -> WorkflowState:
    logger.info("change_planner:update requirements for new prompt attempt=%s", state["requirements_attempts"] + 1)

    previous_requirements = ""
    if state.get("requirements_summary"):
        try:
            previous_requirements = fs_client.read_file(state["requirements_path"])
        except Exception:
            previous_requirements = ""

    raw = invoke_text(
        llm,
        change_planner_prompt(
            original_request=state["user_request"],
            latest_request=state["latest_user_request"],
            current_requirements=previous_requirements,
            prior_feedback=state["latest_failure_summary"],
        ),
    )

    requirements_md, scope = parse_change_scope(raw)
    if not requirements_md:
        requirements_md = previous_requirements or "# Requirements\n\nUnable to parse requirements update."
    fs_client.write_file(REQUIREMENTS_PATH, requirements_md)

    scope_payload = {
        "change_type": scope.get("change_type", "update"),
        "affected_behaviors": scope.get("affected_behaviors", []),
        "likely_affected_files": scope.get("likely_affected_files", []),
        "tests_need_updates": scope.get("tests_need_updates", True),
        "requirements_changed_materially": scope.get("requirements_changed_materially", True),
    }
    fs_client.write_file(CHANGE_SCOPE_PATH, safe_json_dumps(scope_payload))

    return {
        **state,
        "requirements_path": REQUIREMENTS_PATH,
        "requirements_summary": requirements_md[:1000],
        "change_scope": safe_json_dumps(scope_payload),
        "requirements_attempts": state["requirements_attempts"] + 1,
        "requirements_ok": False,
        "final_status": "pending",
    }
