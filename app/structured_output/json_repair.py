from __future__ import annotations

import json
import re

from langchain_openai import ChatOpenAI

SMART_QUOTES = {
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
}


def deterministic_repair(raw: str) -> str:
    text = raw.strip().lstrip("\ufeff")
    text = _replace_smart_quotes(text)
    text = _strip_code_fences(text)
    text = _extract_first_object(text)
    text = _strip_trailing_commas(text)
    return text.strip()


def fallback_repair_with_model(llm: ChatOpenAI, raw: str) -> str:
    prompt = (
        "Repair JSON syntax only. Preserve keys/values and field names exactly. "
        "Do not add fields or prose. Return only valid JSON object.\n\n"
        f"Malformed JSON:\n{raw[:2500]}"
    )
    response = llm.invoke(prompt)
    return getattr(response, "content", "").strip()


def try_parse_json(raw: str) -> dict:
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise json.JSONDecodeError("Expected JSON object", raw, 0)
    return parsed


def _replace_smart_quotes(text: str) -> str:
    for src, dst in SMART_QUOTES.items():
        text = text.replace(src, dst)
    return text


def _strip_code_fences(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text


def _extract_first_object(text: str) -> str:
    start = text.find("{")
    if start < 0:
        return text

    depth = 0
    in_string = False
    escape = False

    for i, ch in enumerate(text[start:], start=start):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    return text[start:]


def _strip_trailing_commas(text: str) -> str:
    out: list[str] = []
    in_string = False
    escape = False
    i = 0

    while i < len(text):
        ch = text[i]
        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue

        if ch == ",":
            j = i + 1
            while j < len(text) and text[j] in " \t\n\r":
                j += 1
            if j < len(text) and text[j] in "]}":
                i += 1
                continue

        out.append(ch)
        i += 1

    return "".join(out)
