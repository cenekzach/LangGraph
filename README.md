# LangGraph Requirements-First MCP Workflow

This project now runs a compact **requirements-first multi-node LangGraph workflow** designed for local models with smaller context windows.

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

## Context-window strategy

To stay practical for ~16k local model contexts, each node prompt is intentionally small:
- only uses minimal state fields needed for that node,
- reads targeted artifact files (not full repo dumps),
- truncates long feedback/log strings,
- stores bulky details in file artifacts instead of graph state.

Prompt builders are in `app/prompts/builders.py`.

## Logs (`docker logs` friendly)

Structured logs are emitted for:
- node start/end,
- routing decisions,
- MCP reads/writes,
- syntax/test outcomes,
- retry cap exits,
- final workflow result.

Examples:
- `requirements_author:start`
- `tester:syntax ok`
- `router:tester -> implementor`
- `workflow:end status=success`

## Run

```bash
source scripts/setup_venv.sh
cp env.example .env
python3 poc_single_node.py "Build a simple calculator app"
```

## Example flow for “Build a simple calculator app”

1. `requirements_author` writes concise calculator requirements markdown.
2. `requirements_reviewer` checks coherence and testability.
3. `implementor` writes calculator source files through filesystem MCP.
4. `tester` writes tests and executes syntax + pytest through Python executor MCP.
5. Failing tests route back to `implementor` with compact failure summary.
6. Passing tests route to `product_reviewer` for requirements-intent alignment.
7. Workflow ends success only when tests pass and product review approves.
