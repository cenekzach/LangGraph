from __future__ import annotations

import re


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
