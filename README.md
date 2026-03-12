# LangGraph iterative CLI app workflow

This project runs a compact multi-node LangGraph workflow designed for smaller local models while making evaluation more **procedural**, deterministic, and debuggable.

## Why the requirements stage was refactored

Recent runs showed a practical failure mode: requirements files were complete, but the reviewer still rejected them based on text fragments that looked truncated. The workflow now treats the requirements markdown artifact as the source of truth and adds procedural integrity checks before asking the model reviewer.

### What changed

- Requirements review now loads **`/workspace/artifacts/requirements.current.md`** directly (full file review, not summary-only review).
- The reviewer logs what it actually read:
  - path
  - character count
  - first 120 chars
  - last 120 chars
  - source type (`full_file`)
- A deterministic integrity preflight runs before model review and writes:
  - **`/workspace/artifacts/requirements_integrity.json`**
- Review output is now severity-based (`blocking_issues`, `non_blocking_issues`, `assumptions_to_record`) instead of strict binary pass/fail.
- Non-blocking gaps are recorded in:
  - **`/workspace/artifacts/requirements.assumptions.md`**
- Routing now uses a **good-enough-to-build threshold** to avoid endless rewrites.

## Graph structure

```text
START
 -> change_planner
 -> requirements_reviewer

requirements_reviewer
 -> terminal                    (internal input/integrity failure)
 -> change_planner              (blocking requirements issues)
 -> assumption_recorder         (non-blocking issues / assumptions)
 -> interface_contract_builder  (requirements good enough)

assumption_recorder
 -> interface_contract_builder

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

## Requirements review policy

The reviewer is now implementation-biased:

- Approve requirements if they are sufficient to build a reasonable implementation.
- Do not require a full formal specification.
- Treat minor unspecified details as assumptions unless they alter core behavior.
- Only block when implementation cannot proceed coherently (contradiction, impossible requirement, missing core behavior, missing success target).

## Smart loop control

Requirements loops are limited more intelligently:

- First failures return blocking issues for rewrite.
- Repeated cycles can de-escalate non-blocking concerns into assumptions.
- If only non-blocking issues remain, assumptions are recorded and implementation proceeds.

This prevents "perfect spec" rewrite loops when the app is already implementable.

## Node responsibilities

- **requirements_reviewer** validates input integrity, reviews full requirements artifact, classifies severity, and writes `/workspace/artifacts/requirements_integrity.json` + `/workspace/artifacts/review.summary.json`.
- **assumption_recorder** writes `/workspace/artifacts/requirements.assumptions.md` from reviewer assumptions.
- **interface_contract_builder** writes `/workspace/artifacts/interface_contract.json` with machine-readable CLI/entrypoint contract.
- **static_contract_checker** catches cheap mismatches before pytest and writes `/workspace/artifacts/contract_check.summary.json`.
- **test_runner** is procedural Python logic: syntax checks, pytest, deterministic CLI scenario checks; writes `/workspace/artifacts/test.summary.json` and `/workspace/artifacts/test.details.json`.
- **playtester** uses bounded exploration and writes `/workspace/artifacts/playtest.summary.json` + `/workspace/artifacts/playtest.log.md`.
- **terminal** writes `/workspace/artifacts/final_status.json` with terminal classification and suggested intervention.

## Artifacts and debugging/checkpoint trail

Workflow keeps in-memory state compact and writes detailed artifacts:

- `/workspace/artifacts/requirements.current.md`
- `/workspace/artifacts/requirements_integrity.json`
- `/workspace/artifacts/requirements.assumptions.md`
- `/workspace/artifacts/review.summary.json`
- `/workspace/artifacts/interface_contract.json`
- `/workspace/artifacts/contract_check.summary.json`
- `/workspace/artifacts/test.summary.json`
- `/workspace/artifacts/test.details.json`
- `/workspace/artifacts/playtest.summary.json`
- `/workspace/artifacts/playtest.log.md`
- `/workspace/artifacts/route_decisions.jsonl`
- `/workspace/artifacts/final_status.json`

`route_decisions.jsonl` records route + reason per transition. Requirements-stage logs should clearly show:

- `requirements_reviewer:loaded ... source=full_file`
- `requirements_reviewer:integrity ok=...`
- `requirements_reviewer:blocking=X non_blocking=Y assumptions=Z`
- `assumption_recorder:wrote N assumptions`
- `router:requirements_reviewer -> ... reason=...`

## Run

```bash
python -m app.workflow "Build or update my CLI app..."
```

Then inspect `/workspace/artifacts/` and logs for requirements source/integrity/routing decisions.
