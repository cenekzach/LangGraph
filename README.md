# LangGraph Requirements-First MCP Workflow

This project runs a compact **requirements-first multi-node LangGraph workflow** designed for local models with smaller context windows.

## Graph structure

```text
START
 -> requirements_author
 -> requirements_reviewer

requirements_reviewer
 -> requirements_author (requirements fail)
 -> implementor (requirements pass)

implementor
 -> tester

tester
 -> implementor (syntax/tests fail)
 -> product_reviewer (syntax/tests pass)

product_reviewer
 -> implementor (implementation mismatch)
 -> requirements_author (requirements need revision)
 -> END (all good)
```

A `state_summarizer` node is used for explicit failure exits after retry caps and writes a concise loop snapshot.

## Why requirements are Markdown

Requirements are written to `/workspace/artifacts/requirements.current.md` as human-readable Markdown so:
- operators can inspect intent quickly,
- later nodes can consume a short summary instead of full chat history,
- acceptance criteria and edge cases stay explicit and testable.

## Structured output strategy (small-model friendly)

The workflow now minimizes fragile raw JSON generation:
- **requirements stay Markdown**,
- **source/test files are emitted as plain text artifact blocks**, not giant JSON-escaped strings,
- JSON is kept for **small schema-bound summaries/review decisions** only.

### Artifact block format (implementor/tester)

`implementor` and `tester` produce deterministic plain text sections:

```text
IMPLEMENTATION_SUMMARY: short summary
FILE_PATH: app/main.py
<python fenced file content>
```

and for tests:

```text
TEST_SUMMARY: short summary
FILE_PATH: tests/test_main.py
<python fenced file content>
```

The app parses `FILE_PATH + fenced content` blocks deterministically and writes files directly via filesystem MCP.

## Structured validation + repair

For nodes that still require JSON (`requirements_reviewer`, `product_reviewer`):

1. **Validate immediately** against compact schemas.
2. If invalid, attempt **deterministic repair first** (strip fences, trim leading/trailing junk, normalize smart quotes, remove trailing commas, extract first JSON object).
3. Re-validate.
4. Only if still invalid, attempt a **narrow fallback JSON repair** prompt that fixes syntax only (no new fields/prose).

This behavior is implemented in:
- `app/structured_output/schemas.py`
- `app/structured_output/validator.py`
- `app/structured_output/json_repair.py`
- `app/structured_output/parsers.py`

## Compact error feedback

When structured output is invalid, nodes send compact targeted feedback instead of echoing huge malformed payloads, for example:
- `Invalid JSON for requirements_review: Missing required field: summary`
- `Invalid implementor artifact format: expected FILE_PATH + fenced content blocks`

This keeps retries focused and context-efficient.

## MCP integrations

### Filesystem MCP (`app/mcp/filesystem_client.py`)
Used by nodes to read/write artifacts and app files:
- requirements markdown,
- source files,
- test files,
- summaries:
  - `/workspace/artifacts/implementation.summary.json`
  - `/workspace/artifacts/test.summary.json`
  - `/workspace/artifacts/review.summary.json`
  - `/workspace/artifacts/loop.summary.md` (failure summary).

### Python executor MCP (`app/mcp/python_executor_client.py`)
Used by `tester` to:
- run Python syntax checks via a compact AST script,
- execute tests (`python -m pytest -q`),
- return normalized stdout/stderr/exit_code for routing.

## Retry loops

Default caps:
- requirements loop: `MAX_REQUIREMENTS_ATTEMPTS=2`
- implement/test loop: `MAX_IMPLEMENTATION_ATTEMPTS=4`
- product review loop: `MAX_REVIEW_ATTEMPTS=2`

If a cap is exceeded, workflow ends `failed` and writes loop summary artifacts.

## Logging

Logs now explicitly show structured-output behavior:
- `structured_output:validate ...`
- `structured_output:repair deterministic attempt/success`
- `structured_output:repair fallback attempt/failed`
- compact feedback logs for invalid responses
- normal router decisions and node progress

Large malformed JSON blobs are not logged.

## Run

```bash
source scripts/setup_venv.sh
cp env.example .env
python3 poc_single_node.py "Build a simple calculator app"
```
