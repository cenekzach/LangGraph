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
    for candidate in _json_candidates(raw):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            repaired = _strip_trailing_commas(candidate)
            if repaired == candidate:
                continue
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                continue
    raise json.JSONDecodeError("Unable to decode JSON payload", raw, 0)


def _json_candidates(raw: str) -> list[str]:
    candidates = [raw.strip()]

    for match in re.finditer(r"```(?:json)?\s*(.*?)\s*```", raw, flags=re.DOTALL | re.IGNORECASE):
        block = match.group(1).strip()
        if block:
            candidates.append(block)

    for chunk in _extract_json_objects(raw):
        chunk = chunk.strip()
        if chunk:
            candidates.append(chunk)

    return list(dict.fromkeys(candidates))


def _extract_json_objects(raw: str) -> list[str]:
    chunks: list[str] = []
    depth = 0
    start = -1
    in_string = False
    escape = False

    for i, char in enumerate(raw):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue

        if char == "{":
            if depth == 0:
                start = i
            depth += 1
        elif char == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start >= 0:
                chunks.append(raw[start : i + 1])
                start = -1

    return chunks


def _strip_trailing_commas(text: str) -> str:
    out: list[str] = []
    in_string = False
    escape = False
    i = 0

    while i < len(text):
        char = text[i]

        if in_string:
            out.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            i += 1
            continue

        if char == '"':
            in_string = True
            out.append(char)
            i += 1
            continue

        if char == ",":
            j = i + 1
            while j < len(text) and text[j] in " \t\n\r":
                j += 1
            if j < len(text) and text[j] in "]}":
                i += 1
                continue

        out.append(char)
        i += 1

    return "".join(out)


def safe_json_dumps(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)
