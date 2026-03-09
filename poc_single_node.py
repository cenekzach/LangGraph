"""Single-node LangGraph PoC for syntax validation."""

from __future__ import annotations

import argparse
import os
from typing import TypedDict

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph


class ValidationState(TypedDict):
    input_text: str
    format_hint: str
    validation_report: str


def validation_node(state: ValidationState, llm: ChatOpenAI) -> ValidationState:
    """Single node: find likely syntax errors and propose fixes."""
    prompt = (
        "You are a strict syntax validation assistant for DevOps workflows. "
        "Analyze the provided text and focus only on syntax/format correctness.\n\n"
        "Target formats may include: Python, Bash, YAML, JSON, Terraform (HCL), "
        "Dockerfile, Kubernetes manifests, GitHub Actions, and INI/TOML.\n\n"
        "Return sections exactly in this order:\n"
        "1) Detected format (and confidence)\n"
        "2) Syntax issues (line-oriented when possible)\n"
        "3) Corrected snippet\n"
        "4) Quick local validation commands to run\n\n"
        "Rules:\n"
        "- Only report syntax/structure issues, not architecture/style suggestions.\n"
        "- If syntax looks valid, explicitly say no syntax errors were found.\n"
        "- Keep response concise and actionable.\n\n"
        f"Format hint: {state['format_hint'] or 'auto-detect'}\n"
        f"Text to validate:\n{state['input_text']}"
    )

    response = llm.invoke(prompt)
    return {
        "input_text": state["input_text"],
        "format_hint": state["format_hint"],
        "validation_report": response.content,
    }


def build_graph(llm: ChatOpenAI):
    """Create a one-node LangGraph workflow."""
    graph = StateGraph(ValidationState)
    graph.add_node("validation_node", lambda state: validation_node(state, llm))
    graph.add_edge(START, "validation_node")
    graph.add_edge("validation_node", END)
    return graph.compile()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a one-node LangGraph syntax validation flow"
    )
    parser.add_argument(
        "input_text",
        help="Code or config text to validate (quote it if it contains spaces)",
    )
    parser.add_argument(
        "--format-hint",
        default="",
        help="Optional format hint (e.g., yaml, json, python, hcl)",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()

    model = os.getenv("OPENAI_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
    base_url = os.getenv("OPENAI_API_BASE", "http://127.0.0.1:8000/v1")
    api_key = os.getenv("OPENAI_API_KEY", "local-dev")

    llm = ChatOpenAI(model=model, base_url=base_url, api_key=api_key, temperature=0)
    app = build_graph(llm)

    result = app.invoke(
        {
            "input_text": args.input_text,
            "format_hint": args.format_hint,
            "validation_report": "",
        }
    )

    print("=== Validation Report ===")
    print(result["validation_report"])


if __name__ == "__main__":
    main()
