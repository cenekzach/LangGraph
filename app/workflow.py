from __future__ import annotations

import argparse
import logging
import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from app.graph.nodes.validator import validator_node
from app.graph.nodes.writer import writer_node
from app.graph.state import WorkflowState
from app.logging_config import configure_logging
from app.mcp.filesystem_client import FilesystemMCPClient

logger = logging.getLogger(__name__)


def build_graph(llm: ChatOpenAI, fs_client: FilesystemMCPClient):
    graph = StateGraph(WorkflowState)

    graph.add_node("writer", lambda state: writer_node(state, llm, fs_client))
    graph.add_node("validator", lambda state: validator_node(state, fs_client))

    graph.add_edge(START, "writer")
    graph.add_edge("writer", "validator")
    graph.add_conditional_edges(
        "validator",
        _next_step,
        {
            "writer": "writer",
            "end": END,
        },
    )
    return graph.compile()


def _next_step(state: WorkflowState) -> str:
    if state["validation_passed"]:
        logger.info("retry_decision decision=end reason=validation_passed")
        return "end"
    if state["attempt_count"] >= state["max_attempts"]:
        logger.info(
            "retry_decision decision=end reason=max_attempts attempt=%s max=%s",
            state["attempt_count"],
            state["max_attempts"],
        )
        return "end"
    logger.info(
        "retry_decision decision=writer attempt=%s max=%s",
        state["attempt_count"],
        state["max_attempts"],
    )
    return "writer"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run two-node LangGraph writer/validator flow")
    parser.add_argument("user_request", help="Artifact request prompt")
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    configure_logging()

    args = parse_args()

    model = os.getenv("OPENAI_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
    base_url = os.getenv("OPENAI_API_BASE", "http://127.0.0.1:8000/v1")
    api_key = os.getenv("OPENAI_API_KEY", "local-dev")

    mcp_url = os.getenv("MCP_FS_BASE_URL", "http://127.0.0.1:8080/mcp")
    max_attempts = int(os.getenv("MAX_ATTEMPTS", "3"))
    workspace_prefix = os.getenv("MCP_WORKSPACE_PREFIX", "")

    llm = ChatOpenAI(model=model, base_url=base_url, api_key=api_key, temperature=0)
    fs_client = FilesystemMCPClient(base_url=mcp_url, workspace_prefix=workspace_prefix)

    logger.info("graph_start")
    fs_client.connect()
    fs_client.discover_tools()

    app = build_graph(llm, fs_client)
    result = app.invoke(
        {
            "user_request": args.user_request,
            "artifact_path": "",
            "artifact_type": "",
            "latest_content_summary": "",
            "validation_passed": False,
            "validation_errors": [],
            "revision_feedback": "",
            "attempt_count": 0,
            "max_attempts": max_attempts,
            "final_status": "pending",
        }
    )

    logger.info(
        "final_graph_outcome status=%s attempts=%s path=%s",
        result["final_status"],
        result["attempt_count"],
        result["artifact_path"],
    )

    print("=== Workflow Result ===")
    print(f"status: {result['final_status']}")
    print(f"artifact_path: {result['artifact_path']}")
    print(f"artifact_type: {result['artifact_type']}")
    print(f"summary: {result['latest_content_summary']}")
    if result["validation_errors"]:
        print("validation_errors:")
        for error in result["validation_errors"]:
            print(f"- {error}")


if __name__ == "__main__":
    main()
