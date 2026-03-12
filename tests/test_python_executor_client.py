from app.mcp.python_executor_client import PythonExecutorMCPClient


def _client() -> PythonExecutorMCPClient:
    return PythonExecutorMCPClient(base_url="http://example.test/mcp")


def test_extract_embedded_payload_reads_json_line():
    payload = PythonExecutorMCPClient._extract_embedded_payload(
        "runner output\n{\"exit_code\": 2, \"stdout\": \"bad\", \"stderr\": \"boom\"}"
    )

    assert payload == {"exit_code": 2, "stdout": "bad", "stderr": "boom"}


def test_extract_command_content_prefers_embedded_exit_code():
    normalized = {
        "stdout": "noise\n{\"exit_code\": 2, \"stdout\": \"pytest errors\", \"stderr\": \"E\"}",
        "stderr": "",
        "exit_code": 0,
        "content": {"stdout": "", "stderr": "", "exit_code": 0},
    }

    content = _client()._extract_command_content(normalized)

    assert content["exit_code"] == 2
    assert content["stdout"] == "pytest errors"
