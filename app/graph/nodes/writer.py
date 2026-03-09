from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from langchain_openai import ChatOpenAI

from app.graph.state import WorkflowState
from app.mcp.filesystem_client import FilesystemMCPClient

logger = logging.getLogger(__name__)

_EXTENSION_BY_TYPE = {
    "python": ".py",
    "json": ".json",
    "yaml": ".yaml",
    "csv": ".csv",
    "markdown": ".md",
    "text": ".txt",
}


def writer_node(state: WorkflowState, llm: ChatOpenAI, fs_client: FilesystemMCPClient) -> WorkflowState:
    logger.info("writer_node_start attempt=%s", state["attempt_count"] + 1)

    attempt = state["attempt_count"] + 1
    generated = _generate_artifact(state, llm)

    artifact_type = generated.get("artifact_type", "text").lower()
    artifact_path = generated.get("artifact_path") or _derive_path(state["user_request"], artifact_type)
    content = generated.get("content", "")
    summary = generated.get("summary", "Artifact generated")

    logger.info("writer_selected_artifact_path path=%s type=%s", artifact_path, artifact_type)
    fs_client.write_file(artifact_path, content)

    return {
        **state,
        "artifact_path": artifact_path,
        "artifact_type": artifact_type,
        "latest_content_summary": summary,
        "attempt_count": attempt,
        "final_status": "pending",
    }


def _generate_artifact(state: WorkflowState, llm: ChatOpenAI) -> dict[str, str]:
    feedback = state["revision_feedback"] or "No revision feedback yet."
    prompt = (
        "Create exactly one artifact for the user request. "
        "Return JSON only with keys: artifact_type, artifact_path, summary, content. "
        "artifact_type must be one of: python,json,yaml,csv,markdown,text. "
        "artifact_path must include file extension.\n"
        f"User request: {state['user_request']}\n"
        f"Revision feedback: {feedback}\n"
    )
    response = llm.invoke(prompt)
    text = response.content if isinstance(response.content, str) else str(response.content)

    try:
        parsed = json.loads(_strip_code_fence(text))
    except json.JSONDecodeError:
        logger.warning("writer_response_parse_failed falling_back=true")
        parsed = {
            "artifact_type": "text",
            "artifact_path": _derive_path(state["user_request"], "text"),
            "summary": "Fallback plain text artifact",
            "content": text,
        }

    return {k: str(v) for k, v in parsed.items()}


def _derive_path(user_request: str, artifact_type: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", user_request.lower()).strip("-")
    slug = slug[:50] or "artifact"
    ext = _EXTENSION_BY_TYPE.get(artifact_type, ".txt")
    return str(Path("artifacts") / f"{slug}{ext}")


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", stripped)
        stripped = stripped.removesuffix("```").strip()
    return stripped
