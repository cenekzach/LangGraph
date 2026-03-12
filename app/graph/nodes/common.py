from __future__ import annotations

import json
from typing import Any

from langchain_openai import ChatOpenAI

from app.structured_output.validator import parse_and_validate_json


def invoke_text(llm: ChatOpenAI, prompt: str) -> str:
    response = llm.invoke(prompt)
    return getattr(response, "content", "").strip()


def invoke_json(
    llm: ChatOpenAI,
    prompt: str,
    *,
    schema_name: str | None = None,
    node_name: str = "node",
    allow_fallback_repair: bool = False,
) -> dict[str, Any]:
    raw = invoke_text(llm, prompt)
    if schema_name:
        return parse_and_validate_json(
            raw=raw,
            schema_name=schema_name,
            node_name=node_name,
            llm_for_fallback=llm if allow_fallback_repair else None,
        )
    return json.loads(raw)


def safe_json_dumps(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)
