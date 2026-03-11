from types import SimpleNamespace

from app.graph.nodes.common import invoke_json


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
