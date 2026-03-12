from __future__ import annotations

import json
import logging

from langchain_openai import ChatOpenAI

from app.structured_output.json_repair import (
    deterministic_repair,
    fallback_repair_with_model,
    try_parse_json,
)
from app.structured_output.schemas import validate_schema

logger = logging.getLogger(__name__)


class StructuredOutputError(ValueError):
    pass


def parse_and_validate_json(
    *,
    raw: str,
    schema_name: str,
    node_name: str,
    llm_for_fallback: ChatOpenAI | None = None,
) -> dict:
    logger.info("structured_output:validate %s %s", node_name, schema_name)

    parsed, err = _try_parse_and_validate(raw, schema_name)
    if parsed is not None:
        logger.info("structured_output:validate pass")
        return parsed

    logger.warning("structured_output:validate failed err=%s", err)
    logger.info("structured_output:repair deterministic attempt")
    repaired = deterministic_repair(raw)
    parsed, err = _try_parse_and_validate(repaired, schema_name)
    if parsed is not None:
        logger.info("structured_output:repair deterministic success")
        return parsed

    logger.warning("structured_output:repair deterministic failed err=%s", err)

    if llm_for_fallback is not None:
        logger.info("structured_output:repair fallback attempt")
        fallback_raw = fallback_repair_with_model(llm_for_fallback, raw)
        parsed, err = _try_parse_and_validate(fallback_raw, schema_name)
        if parsed is not None:
            logger.info("structured_output:repair fallback success")
            return parsed
        logger.error("structured_output:repair fallback failed err=%s", err)

    raise StructuredOutputError(f"Invalid JSON for {schema_name}: {err}")


def _try_parse_and_validate(raw: str, schema_name: str) -> tuple[dict | None, str | None]:
    try:
        parsed = try_parse_json(raw)
    except json.JSONDecodeError as exc:
        return None, _compact_json_error(raw, exc)

    schema_error = validate_schema(parsed, schema_name)
    if schema_error:
        return None, schema_error
    return parsed, None


def _compact_json_error(raw: str, exc: json.JSONDecodeError) -> str:
    snippet = (raw or "").strip().replace("\n", " ")
    snippet = snippet[:160]
    return f"{exc.msg} near pos {exc.pos}. excerpt='{snippet}'"
