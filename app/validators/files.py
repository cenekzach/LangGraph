from __future__ import annotations

import ast
import csv
import io
import json
from pathlib import Path

import yaml


def validate_artifact(path: str, artifact_type: str, content: str) -> list[str]:
    errors: list[str] = []
    suffix = Path(path).suffix.lower()

    if not content.strip():
        errors.append("File is empty.")

    normalized = artifact_type.lower()
    if normalized == "python":
        try:
            ast.parse(content)
        except SyntaxError as exc:
            errors.append(f"Python syntax error at line {exc.lineno}: {exc.msg}")
        if suffix != ".py":
            errors.append("Path extension should be .py for python artifacts.")
    elif normalized == "json":
        try:
            json.loads(content)
        except json.JSONDecodeError as exc:
            errors.append(f"JSON parse error at line {exc.lineno}: {exc.msg}")
        if suffix != ".json":
            errors.append("Path extension should be .json for json artifacts.")
    elif normalized == "yaml":
        try:
            yaml.safe_load(content)
        except yaml.YAMLError as exc:
            errors.append(f"YAML parse error: {exc}")
        if suffix not in {".yaml", ".yml"}:
            errors.append("Path extension should be .yaml or .yml for yaml artifacts.")
    elif normalized == "csv":
        try:
            rows = list(csv.reader(io.StringIO(content)))
            if not rows:
                errors.append("CSV has no rows.")
            widths = {len(row) for row in rows}
            if len(widths) > 1:
                errors.append("CSV rows have inconsistent column counts.")
        except csv.Error as exc:
            errors.append(f"CSV parse error: {exc}")
        if suffix != ".csv":
            errors.append("Path extension should be .csv for csv artifacts.")
    elif normalized == "markdown":
        if suffix not in {".md", ".markdown"}:
            errors.append("Path extension should be .md or .markdown for markdown artifacts.")
    else:
        if suffix not in {".txt", ""}:
            errors.append("Text artifacts should use .txt extension when extension is present.")

    return errors
