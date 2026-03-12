from __future__ import annotations

import re


def canonicalize_test_path(path: str) -> str:
    raw = (path or "").strip().replace("\\", "/")
    if not raw:
        return ""
    raw = raw.lstrip("./")

    if raw.startswith("/workspace/"):
        raw = raw[len("/workspace/") :]
    elif raw.startswith("workspace/"):
        raw = raw[len("workspace/") :]

    filename = raw.split("/")[-1]
    if raw.startswith("tests/"):
        return raw
    if filename.startswith("test_") and filename.endswith(".py"):
        return f"tests/{filename}"
    if raw.endswith(".py") and "/tests/" in f"/{raw}":
        idx = raw.find("tests/")
        return raw[idx:]
    return raw


def parse_artifact_blocks(raw: str) -> list[dict[str, str]]:
    pattern = re.compile(r"FILE_PATH:\s*(.+?)\n```[^\n]*\n(.*?)\n```", re.DOTALL)
    blocks: list[dict[str, str]] = []
    for match in pattern.finditer(raw):
        path = match.group(1).strip()
        content = match.group(2)
        if path and content.strip():
            blocks.append({"path": path, "content": content})
    return blocks


def parse_tagged_summary(raw: str, tag: str) -> str:
    match = re.search(rf"{re.escape(tag)}:\s*(.+)", raw)
    if not match:
        return ""
    return match.group(1).strip()
