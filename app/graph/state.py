from __future__ import annotations

from typing import Literal, TypedDict


class WorkflowState(TypedDict):
    task_id: str
    user_request: str
    latest_user_request: str
    requirements_path: str
    requirements_char_count: int
    requirements_integrity_ok: bool
    requirements_review_source: str
    requirements_summary: str
    blocking_issues: list[str]
    non_blocking_issues: list[str]
    assumptions_to_record: list[str]
    requirements_review_summary: str
    interface_contract_path: str
    interface_contract_summary: str
    change_scope: str
    requirements_ok: bool
    requirements_feedback: str
    source_paths: list[str]
    test_paths: list[str]
    implementation_summary: str
    contract_check_ok: bool
    contract_check_summary: str
    deterministic_test_summary: str
    latest_failure_summary: str
    syntax_ok: bool
    pytest_ok: bool
    scenario_ok: bool
    tests_ok: bool
    test_summary: str
    playtest_ok: bool
    playtest_summary: str
    play_actions_attempted: list[int]
    product_review_ok: bool
    product_review_summary: str
    last_route_reason: str
    failure_category: str
    attempt_counts: dict[str, int]
    requirements_attempts: int
    implementation_attempts: int
    playtest_attempts: int
    review_attempts: int
    max_requirements_attempts: int
    max_implementation_attempts: int
    max_playtest_attempts: int
    max_review_attempts: int
    final_status: Literal[
        "pending",
        "success",
        "failed_requirements",
        "failed_implementation",
        "failed_tests",
        "failed_playtest",
        "failed_review",
        "failed_internal_error",
    ]
