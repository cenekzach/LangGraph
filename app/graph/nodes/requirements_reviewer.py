from __future__ import annotations

import logging

from langchain_openai import ChatOpenAI

from app.graph.nodes.common import invoke_json, safe_json_dumps
from app.graph.state import WorkflowState
from app.mcp.filesystem_client import FilesystemMCPClient
from app.prompts.builders import requirements_review_prompt
from app.structured_output.validator import StructuredOutputError

logger = logging.getLogger(__name__)

REQUIREMENTS_PATH = "/workspace/artifacts/requirements.current.md"
REQUIREMENTS_INTEGRITY_PATH = "/workspace/artifacts/requirements_integrity.json"
REVIEW_SUMMARY_PATH = "/workspace/artifacts/review.summary.json"
_SUSPICIOUS_ENDINGS = (" outpu", " acti", "If scripted acti", "Replay mode outpu")
_EXPECTED_SECTIONS = ("#", "success", "test")


def requirements_reviewer_node(
    state: WorkflowState,
    llm: ChatOpenAI,
    fs_client: FilesystemMCPClient,
) -> WorkflowState:
    logger.info("requirements_reviewer:start")

    requirements_path = REQUIREMENTS_PATH
    try:
        requirements_md = fs_client.read_file(requirements_path)
    except Exception:
        requirements_md = ""

    char_count = len(requirements_md)
    logger.info(
        "requirements_reviewer:loaded path=%s chars=%s source=full_file",
        requirements_path,
        char_count,
    )
    logger.info("requirements_reviewer:head=%r", requirements_md[:120])
    logger.info("requirements_reviewer:tail=%r", requirements_md[-120:] if requirements_md else "")

    integrity = _check_requirements_integrity(requirements_md, requirements_path)
    fs_client.write_file(REQUIREMENTS_INTEGRITY_PATH, safe_json_dumps(integrity))
    logger.info("requirements_reviewer:integrity ok=%s", integrity["ok"])

    if not integrity["ok"]:
        reason = integrity["issues"][0] if integrity["issues"] else "requirements_input_invalid"
        logger.warning("requirements_reviewer:preflight_failed reason=%s", reason)
        return {
            **state,
            "requirements_path": requirements_path,
            "requirements_char_count": char_count,
            "requirements_integrity_ok": False,
            "requirements_review_source": "full_file",
            "requirements_ok": False,
            "blocking_issues": [],
            "non_blocking_issues": [],
            "assumptions_to_record": [],
            "requirements_review_summary": f"preflight failed: {reason}",
            "requirements_feedback": f"internal_error:{reason}",
            "latest_failure_summary": f"requirements preflight failed: {reason}",
            "final_status": "failed_internal_error",
            "failure_category": "internal_error",
            "last_route_reason": reason,
        }

    try:
        review = invoke_json(
            llm,
            requirements_review_prompt(requirements_md),
            schema_name="requirements_review",
            node_name="requirements_reviewer",
            allow_fallback_repair=True,
        )
    except StructuredOutputError as exc:
        feedback = str(exc)
        logger.warning("compact_feedback:requirements_reviewer %s", feedback)
        return {
            **state,
            "requirements_path": requirements_path,
            "requirements_char_count": char_count,
            "requirements_integrity_ok": True,
            "requirements_review_source": "full_file",
            "requirements_ok": False,
            "requirements_feedback": feedback,
            "blocking_issues": ["requirements_review_parse_error"],
            "non_blocking_issues": [],
            "assumptions_to_record": [],
            "requirements_review_summary": feedback,
            "latest_failure_summary": feedback,
        }

    blocking_issues = _normalize_list(review.get("blocking_issues", []))
    non_blocking_issues = _normalize_list(review.get("non_blocking_issues", []))
    assumptions_to_record = _normalize_list(review.get("assumptions_to_record", []))
    review_summary = str(review.get("review_summary", "requirements reviewed")).strip()

    if state["requirements_attempts"] >= 2 and not blocking_issues and non_blocking_issues:
        assumptions_to_record = _dedupe(assumptions_to_record + non_blocking_issues)
        non_blocking_issues = []
        review_summary = f"{review_summary} (de-escalated to assumptions after repeated cycles)"

    ok = not blocking_issues
    logger.info(
        "requirements_reviewer:blocking=%s non_blocking=%s assumptions=%s",
        len(blocking_issues),
        len(non_blocking_issues),
        len(assumptions_to_record),
    )

    summary_payload = {
        "requirements_ok": ok,
        "blocking_issues": blocking_issues,
        "non_blocking_issues": non_blocking_issues,
        "assumptions_to_record": assumptions_to_record,
        "review_summary": review_summary,
        "source": "full_file",
        "requirements_path": requirements_path,
        "requirements_char_count": char_count,
    }
    fs_client.write_file(REVIEW_SUMMARY_PATH, safe_json_dumps(summary_payload))

    return {
        **state,
        "requirements_path": requirements_path,
        "requirements_char_count": char_count,
        "requirements_integrity_ok": True,
        "requirements_review_source": "full_file",
        "requirements_ok": ok,
        "requirements_feedback": "\n".join(blocking_issues),
        "blocking_issues": blocking_issues,
        "non_blocking_issues": non_blocking_issues,
        "assumptions_to_record": assumptions_to_record,
        "requirements_review_summary": review_summary,
        "requirements_summary": review_summary,
        "latest_failure_summary": "; ".join(blocking_issues[:5]) if blocking_issues else "",
    }


def _normalize_list(items: object) -> list[str]:
    if not isinstance(items, list):
        return []
    return [str(i).strip() for i in items if str(i).strip()]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def _check_requirements_integrity(content: str, path: str) -> dict:
    issues: list[str] = []
    stripped = content.strip()
    if not content:
        issues.append("requirements_input_missing")
    if content and not stripped:
        issues.append("requirements_input_empty")
    if len(content) < 80:
        issues.append("requirements_input_too_short")

    last_line = content.splitlines()[-1] if content.splitlines() else ""
    if last_line and not last_line.endswith(('.', '!', '?', '`', ')', ']', ':')) and len(last_line) < 24:
        issues.append("requirements_input_truncated")

    if any(stripped.endswith(fragment) for fragment in _SUSPICIOUS_ENDINGS):
        issues.append("requirements_input_truncated")

    lowered = stripped.lower()
    missing_sections = [section for section in _EXPECTED_SECTIONS if section not in lowered]
    if len(missing_sections) >= 2:
        issues.append("requirements_input_incomplete")

    suspected_truncation = any("truncated" in issue for issue in issues)
    return {
        "ok": not issues,
        "path": path,
        "char_count": len(content),
        "suspected_truncation": suspected_truncation,
        "issues": sorted(set(issues)),
    }
