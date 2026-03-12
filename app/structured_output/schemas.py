from __future__ import annotations

from typing import Any


SCHEMAS: dict[str, dict[str, Any]] = {
    "requirements_review": {
        "required": {
            "requirements_ok": bool,
            "blocking_issues": list,
            "non_blocking_issues": list,
            "assumptions_to_record": list,
            "review_summary": str,
        }
    },
    "product_review": {
        "required": {
            "product_review_ok": bool,
            "route": str,
            "summary": str,
        },
        "enum": {"route": {"end", "implementor", "change_planner"}},
    },
}


def validate_schema(data: dict[str, Any], schema_name: str) -> str | None:
    schema = SCHEMAS.get(schema_name)
    if not schema:
        return f"Unknown schema: {schema_name}"

    required = schema.get("required", {})
    for field, expected_type in required.items():
        if field not in data:
            return f"Missing required field: {field}"
        if not isinstance(data[field], expected_type):
            return f"Invalid type for field '{field}': expected {expected_type.__name__}"

    enums = schema.get("enum", {})
    for field, allowed in enums.items():
        value = data.get(field)
        if value not in allowed:
            return f"Invalid value for field '{field}': expected one of {sorted(allowed)}"

    return None
