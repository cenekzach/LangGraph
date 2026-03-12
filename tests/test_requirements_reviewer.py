from types import SimpleNamespace

from app.graph.nodes.assumption_recorder import assumption_recorder_node
from app.graph.nodes.requirements_reviewer import requirements_reviewer_node


class DummyLLM:
    def __init__(self, content: str):
        self._content = content

    def invoke(self, _prompt: str):
        return SimpleNamespace(content=self._content)


class DummyFSClient:
    def __init__(self, requirements_text: str):
        self.requirements_text = requirements_text
        self.writes: list[tuple[str, str]] = []

    def read_file(self, _path: str) -> str:
        return self.requirements_text

    def write_file(self, path: str, content: str):
        self.writes.append((path, content))


def _state():
    return {
        "task_id": "task-1",
        "user_request": "Build app",
        "latest_user_request": "Build app",
        "requirements_path": "/workspace/artifacts/requirements.current.md",
        "requirements_char_count": 0,
        "requirements_integrity_ok": False,
        "requirements_review_source": "none",
        "requirements_summary": "",
        "blocking_issues": [],
        "non_blocking_issues": [],
        "assumptions_to_record": [],
        "requirements_review_summary": "",
        "interface_contract_path": "/workspace/artifacts/interface_contract.json",
        "interface_contract_summary": "",
        "change_scope": "{}",
        "requirements_ok": False,
        "requirements_feedback": "",
        "source_paths": [],
        "test_paths": [],
        "implementation_summary": "",
        "contract_check_ok": False,
        "contract_check_summary": "",
        "deterministic_test_summary": "",
        "latest_failure_summary": "",
        "syntax_ok": False,
        "pytest_ok": False,
        "scenario_ok": False,
        "tests_ok": False,
        "test_summary": "",
        "playtest_ok": False,
        "playtest_summary": "",
        "play_actions_attempted": [],
        "product_review_ok": False,
        "product_review_summary": "",
        "last_route_reason": "",
        "failure_category": "",
        "attempt_counts": {"requirements": 0, "implementation": 0, "playtest": 0, "review": 0},
        "requirements_attempts": 0,
        "implementation_attempts": 0,
        "playtest_attempts": 0,
        "review_attempts": 0,
        "max_requirements_attempts": 2,
        "max_implementation_attempts": 4,
        "max_playtest_attempts": 3,
        "max_review_attempts": 2,
        "final_status": "pending",
    }


def test_requirements_reviewer_short_input_fails_preflight_without_llm_call():
    fs = DummyFSClient("Replay mode outpu")
    llm = DummyLLM('{"requirements_ok": true, "blocking_issues": [], "non_blocking_issues": [], "assumptions_to_record": [], "review_summary": "ok"}')

    out = requirements_reviewer_node(_state(), llm, fs)

    assert out["final_status"] == "failed_internal_error"
    assert out["requirements_integrity_ok"] is False
    assert any("requirements_integrity.json" in path for path, _ in fs.writes)


def test_requirements_reviewer_sets_severity_fields_and_assumptions():
    requirements = """# Requirements\n\nPurpose is clear.\n\nSuccess: pytest passes.\n\nTest via deterministic CLI actions.\n"""
    fs = DummyFSClient(requirements)
    llm = DummyLLM(
        '{"requirements_ok": true, "blocking_issues": [], "non_blocking_issues": ["exact exit code unspecified"], '
        '"assumptions_to_record": ["malformed --actions exits with code 2"], "review_summary": "good enough"}'
    )

    out = requirements_reviewer_node(_state(), llm, fs)

    assert out["requirements_ok"] is True
    assert out["blocking_issues"] == []
    assert out["non_blocking_issues"] == ["exact exit code unspecified"]
    assert out["assumptions_to_record"] == ["malformed --actions exits with code 2"]


def test_assumption_recorder_writes_markdown_artifact():
    fs = DummyFSClient("ignored")
    state = _state()
    state["assumptions_to_record"] = ["menu numbering starts at 1", "menu numbering starts at 1"]

    out = assumption_recorder_node(state, fs)

    assert out["assumptions_to_record"] == ["menu numbering starts at 1"]
    path, content = fs.writes[-1]
    assert path.endswith("requirements.assumptions.md")
    assert "menu numbering starts at 1" in content
