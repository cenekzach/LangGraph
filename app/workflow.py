from __future__ import annotations

import argparse
import logging
import os
import uuid

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from app.graph.nodes import (
    implementor_node,
    product_reviewer_node,
    requirements_author_node,
    requirements_reviewer_node,
    state_summarizer_node,
    tester_node,
)
from app.graph.state import WorkflowState
from app.logging_config import configure_logging
from app.mcp.filesystem_client import FilesystemMCPClient
from app.mcp.python_executor_client import PythonExecutorMCPClient

logger = logging.getLogger(__name__)


def build_graph(llm: ChatOpenAI, fs: FilesystemMCPClient, pyexec: PythonExecutorMCPClient):
    graph = StateGraph(WorkflowState)

    graph.add_node("requirements_author", lambda s: requirements_author_node(s, llm, fs))
    graph.add_node("requirements_reviewer", lambda s: requirements_reviewer_node(s, llm, fs))
    graph.add_node("implementor", lambda s: implementor_node(s, llm, fs))
    graph.add_node("tester", lambda s: tester_node(s, llm, fs, pyexec))
    graph.add_node("product_reviewer", lambda s: product_reviewer_node(s, llm, fs))
    graph.add_node("state_summarizer", lambda s: state_summarizer_node(s, fs))

    graph.add_edge(START, "requirements_author")
    graph.add_edge("requirements_author", "requirements_reviewer")
    graph.add_conditional_edges("requirements_reviewer", route_requirements, {
        "requirements_author": "requirements_author",
        "implementor": "implementor",
        "state_summarizer": "state_summarizer",
    })
    graph.add_edge("implementor", "tester")
    graph.add_conditional_edges("tester", route_tester, {
        "implementor": "implementor",
        "product_reviewer": "product_reviewer",
        "state_summarizer": "state_summarizer",
    })
    graph.add_conditional_edges("product_reviewer", route_product_review, {
        "implementor": "implementor",
        "requirements_author": "requirements_author",
        "state_summarizer": "state_summarizer",
        "end": END,
    })
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
    logger.info("router:requirements_reviewer -> requirements_author")
    return "requirements_author"


def route_tester(state: WorkflowState) -> str:
    if state["tests_ok"]:
        logger.info("router:tester -> product_reviewer")
        return "product_reviewer"
    if state["implementation_attempts"] >= state["max_implementation_attempts"]:
        logger.info("router:tester -> state_summarizer reason=max_implementation_attempts")
        state["final_status"] = "failed"
        return "state_summarizer"
    logger.info("router:tester -> implementor")
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
    if state["product_review_summary"].startswith("requirements_author:"):
        logger.info("router:product_reviewer -> requirements_author")
        return "requirements_author"
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
        "requirements_path": "/workspace/artifacts/requirements.current.md",
        "requirements_summary": "",
        "requirements_ok": False,
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
        "max_requirements_attempts": int(os.getenv("MAX_REQUIREMENTS_ATTEMPTS", "2")),
        "max_implementation_attempts": int(os.getenv("MAX_IMPLEMENTATION_ATTEMPTS", "4")),
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
