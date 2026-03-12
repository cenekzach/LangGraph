from app.workflow import (
    route_playtester,
    route_product_review,
    route_requirements,
    route_static_contract,
    route_test_runner,
)


def base_state():
    return {
        "task_id": "t1",
        "requirements_ok": False,
        "requirements_attempts": 0,
        "max_requirements_attempts": 2,
        "blocking_issues": [],
        "non_blocking_issues": [],
        "assumptions_to_record": [],
        "contract_check_ok": False,
        "tests_ok": False,
        "implementation_attempts": 0,
        "max_implementation_attempts": 4,
        "playtest_ok": False,
        "playtest_attempts": 0,
        "max_playtest_attempts": 3,
        "product_review_ok": False,
        "review_attempts": 0,
        "max_review_attempts": 2,
        "product_review_summary": "",
        "final_status": "pending",
        "failure_category": "",
        "last_route_reason": "",
    }


def test_requirements_route_to_contract_builder_on_pass():
    s = base_state()
    s["requirements_ok"] = True
    assert route_requirements(s) == "interface_contract_builder"


def test_requirements_route_to_assumptions_when_non_blocking():
    s = base_state()
    s["requirements_ok"] = True
    s["non_blocking_issues"] = ["minor formatting"]
    assert route_requirements(s) == "assumption_recorder"


def test_requirements_route_to_change_planner_when_blocking():
    s = base_state()
    s["blocking_issues"] = ["missing core behavior"]
    assert route_requirements(s) == "change_planner"


def test_requirements_route_to_terminal_on_internal_error():
    s = base_state()
    s["final_status"] = "failed_internal_error"
    s["last_route_reason"] = "requirements_input_truncated"
    assert route_requirements(s) == "terminal"


def test_contract_route_to_test_runner_on_pass():
    s = base_state()
    s["contract_check_ok"] = True
    assert route_static_contract(s) == "test_runner"


def test_test_runner_route_to_playtester_on_pass():
    s = base_state()
    s["tests_ok"] = True
    assert route_test_runner(s) == "playtester"


def test_playtester_route_to_product_reviewer_on_pass():
    s = base_state()
    s["playtest_ok"] = True
    assert route_playtester(s) == "product_reviewer"


def test_product_review_route_to_change_planner():
    s = base_state()
    s["product_review_summary"] = "change_planner:rewrite acceptance criteria"
    assert route_product_review(s) == "change_planner"
