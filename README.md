# LangGraph iterative CLI app workflow

This project runs a compact multi-node LangGraph workflow designed for smaller local models while making evaluation more **procedural**, deterministic, and debuggable.

## Why this workflow was refactored

The pipeline now explicitly separates:

- **MCP transport success** (`ok=True` means tool call reached MCP and returned) and
- **inner command success** (e.g. `exit_code == 0`, `valid == True`).

Routing and pass/fail decisions use inner execution fields, not loose string interpretation.

## Graph structure

```text
START
 -> change_planner
 -> requirements_reviewer

requirements_reviewer
 -> change_planner               (requirements need revision)
 -> interface_contract_builder   (requirements acceptable)

interface_contract_builder
 -> implementor

implementor
 -> test_author

test_author
 -> static_contract_checker

static_contract_checker
 -> implementor                  (structural mismatch)
 -> test_runner                  (structural checks pass)

test_runner
 -> implementor                  (syntax/pytest/scenario fail)
 -> playtester                   (deterministic checks pass)

playtester
 -> implementor                  (bugs, dead-end loops, parse failures)
 -> product_reviewer             (sufficient confidence)

product_reviewer
 -> implementor                  (implementation issue)
 -> change_planner               (requirements issue)
 -> END                          (success)

Any phase exceeding retry caps routes to terminal -> END with explicit failure status.
```

## Node responsibilities

- **interface_contract_builder** writes `/workspace/artifacts/interface_contract.json` with machine-readable CLI/entrypoint contract.
- **static_contract_checker** catches cheap mismatches before pytest (missing files, unresolved test imports/symbols, parse failures) and writes `/workspace/artifacts/contract_check.summary.json`.
- **test_runner** is procedural Python logic: syntax checks, pytest, deterministic CLI scenario checks; writes `/workspace/artifacts/test.summary.json` and `/workspace/artifacts/test.details.json`.
- **playtester** uses bounded exploration (frontier search), only valid parsed actions, state hashing/dedupe, and early stop on stagnation; writes `/workspace/artifacts/playtest.summary.json` + `/workspace/artifacts/playtest.log.md`.
- **terminal** writes `/workspace/artifacts/final_status.json` with terminal classification and suggested intervention.

## Structured MCP result shapes

`PythonExecutorMCPClient` now returns stable objects:

- `python_syntax_check(path)` -> `{ok, valid, path, error_type, error_message, line, offset, duration_ms}`
- `python_run_tests(command)` -> `{ok, exit_code, stdout, stderr, timed_out, duration_ms}` (pytest output is parsed so inner exit code is honored when wrapped in text)
- `python_run_script(path, args, stdin_text, timeout_seconds, cwd)` -> `{ok, exit_code, stdout, stderr, timed_out, duration_ms}`

Deterministic tests are written under `tests/` only, and pytest is invoked with `-p no:cacheprovider` to avoid cache writes in read-only workspaces.

This avoids false positives where transport success was mistaken for test pass.

## Explicit terminal statuses

Final status is always one of:

- `success`
- `failed_requirements`
- `failed_implementation`
- `failed_tests`
- `failed_playtest`
- `failed_review`
- `failed_internal_error`

No vague `pending` terminal outcomes after retries are exhausted.

## Artifacts and debugging/checkpoint trail

Workflow keeps in-memory state compact and writes detailed artifacts:

- `/workspace/artifacts/interface_contract.json`
- `/workspace/artifacts/contract_check.summary.json`
- `/workspace/artifacts/test.summary.json`
- `/workspace/artifacts/test.details.json`
- `/workspace/artifacts/playtest.summary.json`
- `/workspace/artifacts/playtest.log.md`
- `/workspace/artifacts/route_decisions.jsonl`
- `/workspace/artifacts/final_status.json`

`route_decisions.jsonl` records route + reason per transition for postmortem debugging.

## Run

```bash
python -m app.workflow "Build or update my CLI app..."
```

Then inspect `/workspace/artifacts/` and logs (`test_runner:pytest exit_code=...`, `router:* reason=...`, `workflow:end ...`).
