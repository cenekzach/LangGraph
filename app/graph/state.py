from __future__ import annotations

from typing import Literal, TypedDict


class WorkflowState(TypedDict):
    user_request: str
    artifact_path: str
    artifact_type: str
    latest_content_summary: str
    validation_passed: bool
    validation_errors: list[str]
    revision_feedback: str
    attempt_count: int
    max_attempts: int
    final_status: Literal["pending", "success", "failed"]
