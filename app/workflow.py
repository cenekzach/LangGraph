from __future__ import annotations

import argparse
import logging
import os
import uuid

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from app.graph.nodes import (
    change_planner_node,
    implementor_node,
    playtester_node,
    product_reviewer_node,
    requirements_reviewer_node,
    state_summarizer_node,
    test_author_node,
    test_runner_node,
)
from app.graph.state import WorkflowState
from app.logging_config import configure_logging
from app.mcp.filesystem_client import FilesystemMCPClient
from app.mcp.python_executor_client import PythonExecutorMCPClient

logger = logging.getLogger(__name__)


def build_graph(llm: ChatOpenAI, fs: FilesystemMCPClient, pyexec: PythonExecutorMCPClient):
    graph = StateGraph(WorkflowState)

    graph.add_node("change_planner", lambda s: change_planner_node(s, llm, fs))
    graph.add_node("requirements_reviewer", lambda s: requirements_reviewer_node(s, llm, fs))
    graph.add_node("implementor", lambda s: implementor_node(s, llm, fs))
    graph.add_node("test_author", lambda s: test_author_node(s, llm, fs))
    graph.add_node("test_runner", lambda s: test_runner_node(s, fs, pyexec))
    graph.add_node("playtester", lambda s: playtester_node(s, llm, fs, pyexec))
    graph.add_node("product_reviewer", lambda s: product_reviewer_node(s, llm, fs))
    graph.add_node("state_summarizer", lambda s: state_summarizer_node(s, fs))

    graph.add_edge(START, "change_planner")
    graph.add_edge("change_planner", "requirements_reviewer")
    graph.add_conditional_edges(
        "requirements_reviewer",
        route_requirements,
        {
            "change_planner": "change_planner",
            "implementor": "implementor",
            "state_summarizer": "state_summarizer",
        },
    )
    graph.add_edge("implementor", "test_author")
    graph.add_edge("test_author", "test_runner")
    graph.add_conditional_edges(
        "test_runner",
        route_test_runner,
        {
            "implementor": "implementor",
            "playtester": "playtester",
            "state_summarizer": "state_summarizer",
        },
    )
    graph.add_conditional_edges(
        "playtester",
        route_playtester,
        {
            "implementor": "implementor",
            "product_reviewer": "product_reviewer",
            "state_summarizer": "state_summarizer",
        },
    )
    graph.add_conditional_edges(
        "product_reviewer",
        route_product_review,
        {
            "implementor": "implementor",
            "change_planner": "change_planner",
            "state_summarizer": "state_summarizer",
            "end": END,
        },
    )
    graph.add_edge("state_summarizer", END)
    return graph.compile()


def route_requirements(state: WorkflowState) -> str:
    if state["requirements_ok"]:
        logger.info("router:requirements_reviewer -> implementor")
        return "implementor"
    if state["requirements_attempts"] >= state["max_requirements_attempts"]:
        logger.info("router:requirements_reviewer -> state_summarizer reason=max_requirements_attempts")
        state["final_status"] = "failed"
        return "state_summarizer"
    logger.info("router:requirements_reviewer -> change_planner")
    return "change_planner"


def route_test_runner(state: WorkflowState) -> str:
    if state["tests_ok"]:
        logger.info("router:test_runner -> playtester")
        return "playtester"
    if state["implementation_attempts"] >= state["max_implementation_attempts"]:
        logger.info("router:test_runner -> state_summarizer reason=max_implementation_attempts")
        state["final_status"] = "failed"
        return "state_summarizer"
    logger.info("router:test_runner -> implementor")
    return "implementor"


def route_playtester(state: WorkflowState) -> str:
    if state["playtest_ok"]:
        logger.info("router:playtester -> product_reviewer")
        return "product_reviewer"
    if state["playtest_attempts"] >= state["max_playtest_attempts"]:
        logger.info("router:playtester -> state_summarizer reason=max_playtest_attempts")
        state["final_status"] = "failed"
        return "state_summarizer"
    logger.info("router:playtester -> implementor")
    return "implementor"


def route_product_review(state: WorkflowState) -> str:
    if state["product_review_ok"]:
        logger.info("router:product_reviewer -> END")
        state["final_status"] = "success"
        return "end"
    if state["review_attempts"] >= state["max_review_attempts"]:
        logger.info("router:product_reviewer -> state_summarizer reason=max_review_attempts")
        state["final_status"] = "failed"
        return "state_summarizer"
    if state["product_review_summary"].startswith("change_planner:"):
        logger.info("router:product_reviewer -> change_planner")
        return "change_planner"
    logger.info("router:product_reviewer -> implementor")
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
        "change_scope": "{}",
        "requirements_ok": False,
        "requirements_feedback": "",
        "source_paths": [],
        "test_paths": [],
        "implementation_summary": "",
        "deterministic_test_summary": "",
        "latest_failure_summary": "",
        "tests_ok": False,
        "playtest_ok": False,
        "playtest_summary": "",
        "play_actions_attempted": [],
        "product_review_ok": False,
        "product_review_summary": "",
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
