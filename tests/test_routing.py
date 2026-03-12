from app.workflow import (
    route_playtester,
    route_product_review,
    route_requirements,
    route_test_runner,
)


def base_state():
    return {
        "requirements_ok": False,
        "requirements_attempts": 0,
        "max_requirements_attempts": 2,
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
    }


def test_requirements_route_to_implementor_on_pass():
    s = base_state()
    s["requirements_ok"] = True
    assert route_requirements(s) == "implementor"


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
