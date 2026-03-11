from app.workflow import route_product_review, route_requirements, route_tester


def base_state():
    return {
        "requirements_ok": False,
        "requirements_attempts": 0,
        "max_requirements_attempts": 2,
        "tests_ok": False,
        "implementation_attempts": 0,
        "max_implementation_attempts": 4,
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


def test_tester_route_to_product_reviewer_on_pass():
    s = base_state()
    s["tests_ok"] = True
    assert route_tester(s) == "product_reviewer"


def test_product_review_route_to_requirements_author():
    s = base_state()
    s["product_review_summary"] = "requirements_author:rewrite acceptance criteria"
    assert route_product_review(s) == "requirements_author"
