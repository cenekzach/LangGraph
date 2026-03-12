from __future__ import annotations

from typing import Literal, TypedDict


class WorkflowState(TypedDict):
    task_id: str
    user_request: str
    latest_user_request: str
    requirements_path: str
    requirements_summary: str
    change_scope: str
    requirements_ok: bool
    requirements_feedback: str
    source_paths: list[str]
    test_paths: list[str]
    implementation_summary: str
    deterministic_test_summary: str
    latest_failure_summary: str
    tests_ok: bool
    playtest_ok: bool
    playtest_summary: str
    play_actions_attempted: list[int]
    product_review_ok: bool
    product_review_summary: str
    requirements_attempts: int
    implementation_attempts: int
    playtest_attempts: int
    review_attempts: int
    max_requirements_attempts: int
    max_implementation_attempts: int
    max_playtest_attempts: int
    max_review_attempts: int
    final_status: Literal["pending", "success", "failed"]
