from __future__ import annotations

import logging

from langchain_openai import ChatOpenAI

from app.graph.nodes.common import invoke_json, safe_json_dumps
from app.graph.state import WorkflowState
from app.mcp.filesystem_client import FilesystemMCPClient
from app.prompts.builders import product_review_prompt
from app.structured_output.validator import StructuredOutputError

logger = logging.getLogger(__name__)

REVIEW_SUMMARY_PATH = "/workspace/artifacts/review.summary.json"


def product_reviewer_node(
    state: WorkflowState,
    llm: ChatOpenAI,
    fs_client: FilesystemMCPClient,
) -> WorkflowState:
    logger.info("product_reviewer:start attempt=%s", state["review_attempts"] + 1)
    try:
        review = invoke_json(
            llm,
            product_review_prompt(
                state["requirements_summary"],
                state["implementation_summary"],
                state["test_summary"],
            ),
            schema_name="product_review",
            node_name="product_reviewer",
            allow_fallback_repair=True,
        )
    except StructuredOutputError as exc:
        summary = str(exc)
        logger.warning("compact_feedback:product_reviewer %s", summary)
        fs_client.write_file(
            REVIEW_SUMMARY_PATH,
            safe_json_dumps(
                {
                    "product_review_ok": False,
                    "route": "implementor",
                    "summary": summary,
                }
            ),
        )
        return {
            **state,
            "product_review_ok": False,
            "product_review_summary": f"implementor:{summary}",
            "review_attempts": state["review_attempts"] + 1,
            "latest_failure_summary": summary,
        }

    ok = bool(review.get("product_review_ok", False))
    route = review.get("route", "implementor")
    summary = review.get("summary", "")

    fs_client.write_file(
        REVIEW_SUMMARY_PATH,
        safe_json_dumps({"product_review_ok": ok, "route": route, "summary": summary}),
    )

    return {
        **state,
        "product_review_ok": ok,
        "product_review_summary": f"{route}:{summary}",
        "review_attempts": state["review_attempts"] + 1,
        "latest_failure_summary": "" if ok else summary,
    }
