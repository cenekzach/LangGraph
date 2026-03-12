from types import SimpleNamespace

from app.graph.nodes.common import invoke_json
from app.graph.nodes.implementor import implementor_node
from app.structured_output.parsers import parse_artifact_blocks
from app.structured_output.validator import StructuredOutputError


class DummyLLM:
    def __init__(self, content: str):
        self._content = content

    def invoke(self, _prompt: str):
        return SimpleNamespace(content=self._content)


def test_invoke_json_repairs_markdown_wrapped_json_with_trailing_commas():
    llm = DummyLLM(
        """
Here is the review:
```json
{
  "requirements_ok": true,
  "issues": [],
  "rewrite_instructions": "",
  "summary": "ok",
}
```
"""
    )

    parsed = invoke_json(llm, "ignored", schema_name="requirements_review", node_name="requirements_reviewer")

    assert parsed["summary"] == "ok"


def test_invoke_json_schema_validation_returns_compact_error():
    llm = DummyLLM('{"requirements_ok": true}')

    try:
        invoke_json(llm, "ignored", schema_name="requirements_review", node_name="requirements_reviewer")
    except StructuredOutputError as exc:
        assert "Missing required field" in str(exc)
    else:
        raise AssertionError("Expected StructuredOutputError")


def test_parse_artifact_blocks_reads_plain_text_file_sections():
    raw = (
        "IMPLEMENTATION_SUMMARY: updated\n"
        "FILE_PATH: app/main.py\n"
        "```python\n"
        "print('ok')\n"
        "```\n"
    )

    parsed = parse_artifact_blocks(raw)

    assert parsed == [{"path": "app/main.py", "content": "print('ok')"}]


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


def test_implementor_writes_plain_text_artifact_blocks_without_json_loop():
    llm = DummyLLM(
        "IMPLEMENTATION_SUMMARY: ok\n"
        "FILE_PATH: app/main.py\n"
        "```python\n"
        "print(1)\n"
        "```"
    )
    fs = DummyFSClient()

    out = implementor_node(_base_state(), llm, fs)

    assert out["implementation_attempts"] == 1
    assert out["implementation_summary"] == "ok"
    assert out["source_paths"] == ["app/main.py"]


def test_implementor_returns_compact_feedback_on_invalid_artifact_blocks():
    llm = DummyLLM("not parseable")
    fs = DummyFSClient()

    out = implementor_node(_base_state(), llm, fs)

    assert "Invalid implementor artifact format" in out["latest_failure_summary"]
    assert out["source_paths"] == []
