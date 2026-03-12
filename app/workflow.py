from __future__ import annotations

import argparse
import json
import logging
import os
import uuid

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from app.graph.nodes import (
    change_planner_node,
    implementor_node,
    interface_contract_builder_node,
    playtester_node,
    product_reviewer_node,
    requirements_reviewer_node,
    static_contract_checker_node,
    terminal_node,
    test_author_node,
    test_runner_node,
)
from app.graph.state import WorkflowState
from app.logging_config import configure_logging
from app.mcp.filesystem_client import FilesystemMCPClient
from app.mcp.python_executor_client import PythonExecutorMCPClient

logger = logging.getLogger(__name__)

ROUTE_DECISIONS_PATH = "/workspace/artifacts/route_decisions.jsonl"


def build_graph(llm: ChatOpenAI, fs: FilesystemMCPClient, pyexec: PythonExecutorMCPClient):
    graph = StateGraph(WorkflowState)

    graph.add_node("change_planner", lambda s: change_planner_node(s, llm, fs))
    graph.add_node("requirements_reviewer", lambda s: requirements_reviewer_node(s, llm, fs))
    graph.add_node("interface_contract_builder", lambda s: interface_contract_builder_node(s, fs))
    graph.add_node("implementor", lambda s: implementor_node(s, llm, fs))
    graph.add_node("test_author", lambda s: test_author_node(s, llm, fs))
    graph.add_node("static_contract_checker", lambda s: static_contract_checker_node(s, fs))
    graph.add_node("test_runner", lambda s: test_runner_node(s, fs, pyexec))
    graph.add_node("playtester", lambda s: playtester_node(s, llm, fs, pyexec))
    graph.add_node("product_reviewer", lambda s: product_reviewer_node(s, llm, fs))
    graph.add_node("terminal", lambda s: terminal_node(s, fs))

    graph.add_edge(START, "change_planner")
    graph.add_edge("change_planner", "requirements_reviewer")
    graph.add_conditional_edges(
        "requirements_reviewer",
        route_requirements,
        {
            "change_planner": "change_planner",
            "interface_contract_builder": "interface_contract_builder",
            "terminal": "terminal",
        },
    )
    graph.add_edge("interface_contract_builder", "implementor")
    graph.add_edge("implementor", "test_author")
    graph.add_edge("test_author", "static_contract_checker")
    graph.add_conditional_edges(
        "static_contract_checker",
        route_static_contract,
        {
            "implementor": "implementor",
            "test_runner": "test_runner",
            "terminal": "terminal",
        },
    )
    graph.add_conditional_edges(
        "test_runner",
        route_test_runner,
        {
            "implementor": "implementor",
            "playtester": "playtester",
            "terminal": "terminal",
        },
    )
    graph.add_conditional_edges(
        "playtester",
        route_playtester,
        {
            "implementor": "implementor",
            "product_reviewer": "product_reviewer",
            "terminal": "terminal",
        },
    )
    graph.add_conditional_edges(
        "product_reviewer",
        route_product_review,
        {
            "implementor": "implementor",
            "change_planner": "change_planner",
            "terminal": "terminal",
            "end": END,
        },
    )
    graph.add_edge("terminal", END)
    return graph.compile()


def _record_route(state: WorkflowState, source: str, destination: str, reason: str) -> None:
    state["last_route_reason"] = reason
    line = json.dumps({"from": source, "to": destination, "reason": reason, "task_id": state.get("task_id")})
    os.makedirs(os.path.dirname(ROUTE_DECISIONS_PATH), exist_ok=True)
    with open(ROUTE_DECISIONS_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    logger.info("router:%s -> %s reason=%s", source, destination, reason)


def route_requirements(state: WorkflowState) -> str:
    if state["requirements_ok"]:
        _record_route(state, "requirements_reviewer", "interface_contract_builder", "requirements_ok")
        return "interface_contract_builder"
    if state["requirements_attempts"] >= state["max_requirements_attempts"]:
        state["final_status"] = "failed_requirements"
        state["failure_category"] = "requirements"
        _record_route(state, "requirements_reviewer", "terminal", "max_requirements_attempts")
        return "terminal"
    _record_route(state, "requirements_reviewer", "change_planner", "requirements_revision_needed")
    return "change_planner"


def route_static_contract(state: WorkflowState) -> str:
    if state.get("contract_check_ok"):
        _record_route(state, "static_contract_checker", "test_runner", "contract_ok")
        return "test_runner"
    if state["implementation_attempts"] >= state["max_implementation_attempts"]:
        state["final_status"] = "failed_implementation"
        state["failure_category"] = "implementation"
        _record_route(state, "static_contract_checker", "terminal", "max_implementation_attempts")
        return "terminal"
    _record_route(state, "static_contract_checker", "implementor", "contract_mismatch")
    return "implementor"


def route_test_runner(state: WorkflowState) -> str:
    if state["tests_ok"]:
        _record_route(state, "test_runner", "playtester", "deterministic_checks_passed")
        return "playtester"
    if state["implementation_attempts"] >= state["max_implementation_attempts"]:
        state["final_status"] = "failed_tests"
        state["failure_category"] = "tests"
        _record_route(state, "test_runner", "terminal", "max_implementation_attempts")
        return "terminal"
    _record_route(state, "test_runner", "implementor", "deterministic_checks_failed")
    return "implementor"


def route_playtester(state: WorkflowState) -> str:
    if state["playtest_ok"]:
        _record_route(state, "playtester", "product_reviewer", "playtest_passed")
        return "product_reviewer"
    if state["playtest_attempts"] >= state["max_playtest_attempts"]:
        state["final_status"] = "failed_playtest"
        state["failure_category"] = "playtest"
        _record_route(state, "playtester", "terminal", "max_playtest_attempts")
        return "terminal"
    _record_route(state, "playtester", "implementor", "playtest_bug_detected")
    return "implementor"


def route_product_review(state: WorkflowState) -> str:
    if state["product_review_ok"]:
        state["final_status"] = "success"
        _record_route(state, "product_reviewer", "end", "product_review_ok")
        return "end"
    if state["review_attempts"] >= state["max_review_attempts"]:
        state["final_status"] = "failed_review"
        state["failure_category"] = "review"
        _record_route(state, "product_reviewer", "terminal", "max_review_attempts")
        return "terminal"
    if state["product_review_summary"].startswith("change_planner:"):
        _record_route(state, "product_reviewer", "change_planner", "requirements_need_revision")
        return "change_planner"
    _record_route(state, "product_reviewer", "implementor", "implementation_revision_needed")
    return "implementor"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run requirements-first LangGraph MCP workflow")
    parser.add_argument("user_request", help="Application request")
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    configure_logging()
    args = parse_args()

    llm = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "meta-llama/Llama-3.1-8B-Instruct"),
        base_url=os.getenv("OPENAI_API_BASE", "http://127.0.0.1:8000/v1"),
        api_key=os.getenv("OPENAI_API_KEY", "local-dev"),
        temperature=0,
    )
    fs_client = FilesystemMCPClient(
        base_url=os.getenv("MCP_FS_BASE_URL", "http://127.0.0.1:8080/mcp"),
        workspace_prefix=os.getenv("MCP_WORKSPACE_PREFIX", ""),
    )
    pyexec_client = PythonExecutorMCPClient(
        base_url=os.getenv("MCP_PYTHON_BASE_URL", "http://127.0.0.1:8090/mcp"),
    )

    logger.info("workflow:start")
    fs_client.connect()
    fs_client.discover_tools()
    pyexec_client.connect()
    pyexec_client.discover_tools()

    app = build_graph(llm, fs_client, pyexec_client)
    initial_state: WorkflowState = {
        "task_id": str(uuid.uuid4()),
        "user_request": args.user_request,
        "latest_user_request": args.user_request,
        "requirements_path": "/workspace/artifacts/requirements.current.md",
        "requirements_summary": "",
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
        "max_requirements_attempts": int(os.getenv("MAX_REQUIREMENTS_ATTEMPTS", "2")),
        "max_implementation_attempts": int(os.getenv("MAX_IMPLEMENTATION_ATTEMPTS", "4")),
        "max_playtest_attempts": int(os.getenv("MAX_PLAYTEST_ATTEMPTS", "3")),
        "max_review_attempts": int(os.getenv("MAX_REVIEW_ATTEMPTS", "2")),
        "final_status": "pending",
    }
    result = app.invoke(initial_state)

    logger.info("workflow:end status=%s", result["final_status"])
    print("=== Workflow Result ===")
    print(f"task_id: {result['task_id']}")
    print(f"status: {result['final_status']}")
    print(f"requirements_path: {result['requirements_path']}")
    print(f"source_paths: {result['source_paths']}")
    print(f"test_paths: {result['test_paths']}")
    print(f"summary: {result['product_review_summary'] or result['latest_failure_summary']}")


if __name__ == "__main__":
    main()
