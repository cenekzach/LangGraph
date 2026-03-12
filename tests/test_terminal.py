from app.graph.nodes.terminal import terminal_node


class DummyFSClient:
    def __init__(self):
        self.writes: list[tuple[str, str]] = []

    def write_file(self, path: str, content: str):
        self.writes.append((path, content))


def test_terminal_node_converts_pending_to_failed_internal_error():
    state = {
        "final_status": "pending",
        "failure_category": "",
        "last_route_reason": "",
        "latest_failure_summary": "",
        "attempt_counts": {},
    }
    fs = DummyFSClient()

    out = terminal_node(state, fs)

    assert out["final_status"] == "failed_internal_error"
    assert fs.writes, "terminal node should persist final status artifact"
