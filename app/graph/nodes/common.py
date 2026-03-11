from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


def invoke_text(llm: ChatOpenAI, prompt: str) -> str:
    response = llm.invoke(prompt)
    return getattr(response, "content", "").strip()


def invoke_json(llm: ChatOpenAI, prompt: str) -> dict[str, Any]:
    raw = invoke_text(llm, prompt)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def safe_json_dumps(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)
