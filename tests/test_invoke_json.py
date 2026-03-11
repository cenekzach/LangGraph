from types import SimpleNamespace

from app.graph.nodes.common import invoke_json
from app.graph.nodes.implementor import implementor_node


class DummyLLM:
    def __init__(self, content: str):
        self._content = content

    def invoke(self, _prompt: str):
        return SimpleNamespace(content=self._content)


def test_invoke_json_parses_markdown_wrapped_json_with_trailing_commas():
    llm = DummyLLM(
        """
Here is the plan:
```json
{
  "source_files": [
    {"path": "app/main.py", "content": "print('ok')",},
  ],
  "implementation_summary": "updated",
}
```
"""
    )

    parsed = invoke_json(llm, "ignored")

    assert parsed["implementation_summary"] == "updated"
    assert parsed["source_files"][0]["path"] == "app/main.py"


def test_invoke_json_parses_balanced_json_object_in_freeform_text():
    llm = DummyLLM(
        "Result follows => {\n"
        "  \"requirements_ok\": true,\n"
        "  \"issues\": []\n"
        "} <= end"
    )

    parsed = invoke_json(llm, "ignored")

    assert parsed == {"requirements_ok": True, "issues": []}


class SequencedDummyLLM:
    def __init__(self, responses: list[str]):
        self._responses = responses
        self.calls = 0

    def invoke(self, _prompt: str):
        idx = min(self.calls, len(self._responses) - 1)
        self.calls += 1
        return SimpleNamespace(content=self._responses[idx])


class DummyFSClient:
    def __init__(self):
        self.writes: list[tuple[str, str]] = []

    def write_file(self, path: str, content: str):
        self.writes.append((path, content))


def _base_state():
    return {
        "task_id": "t-1",
        "user_request": "Build a hello world app",
        "requirements_path": "/workspace/artifacts/requirements.current.md",
        "requirements_summary": "Create app",
        "requirements_ok": True,
        "requirements_feedback": "",
        "source_paths": [],
        "test_paths": [],
        "implementation_summary": "",
        "latest_failure_summary": "",
        "test_summary": "",
        "tests_ok": False,
        "product_review_ok": False,
        "product_review_summary": "",
        "requirements_attempts": 0,
        "implementation_attempts": 0,
        "review_attempts": 0,
        "max_requirements_attempts": 2,
        "max_implementation_attempts": 4,
        "max_review_attempts": 2,
        "final_status": "pending",
    }


def test_implementor_retries_with_stricter_prompt_on_invalid_json():
    llm = SequencedDummyLLM(
        responses=[
            "not json",
            '{"source_files": [{"path": "app/main.py", "content": "print(1)"}], "implementation_summary": "ok"}',
        ]
    )
    fs = DummyFSClient()

    out = implementor_node(_base_state(), llm, fs)

    assert llm.calls == 2
    assert out["implementation_summary"] == "ok"
    assert out["source_paths"] == ["app/main.py"]


def test_implementor_falls_back_to_empty_plan_after_two_invalid_payloads():
    llm = SequencedDummyLLM(responses=["not json", "still not json"])
    fs = DummyFSClient()

    out = implementor_node(_base_state(), llm, fs)

    assert llm.calls == 2
    assert out["implementation_summary"].startswith("implementation plan unavailable")
    assert out["source_paths"] == []
