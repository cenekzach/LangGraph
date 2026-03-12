# LangGraph iterative CLI app workflow

This project runs a compact multi-node LangGraph workflow designed for smaller local models while still supporting iterative updates to existing projects.

## Graph structure

```text
START
 -> change_planner
 -> requirements_reviewer

requirements_reviewer
 -> change_planner (requirements need revision)
 -> implementor (requirements acceptable)

implementor
 -> test_author

test_author
 -> test_runner

test_runner
 -> implementor (syntax/pytest/static checks fail)
 -> playtester (deterministic checks pass)

playtester
 -> implementor (bugs/dead ends/flag UX issues)
 -> product_reviewer (playtest confidence acceptable)

product_reviewer
 -> implementor (implementation wrong)
 -> change_planner (requirements wrong)
 -> END (acceptable)
```

## Node responsibilities

- **change_planner**: updates `/workspace/artifacts/requirements.current.md` in Markdown, merges latest user change with existing requirements, and writes compact `/workspace/artifacts/change_scope.json`.
- **requirements_reviewer**: checks coherence, contradictions, ambiguity, acceptance criteria, and deterministic CLI contract (`--actions`, `--exit`, numeric actions).
- **implementor**: makes targeted source edits and writes `/workspace/artifacts/implementation.summary.json`.
- **test_author**: writes deterministic pytest/static scenario tests and updates `/workspace/artifacts/test.summary.json` metadata.
- **test_runner**: procedurally computes pass/fail from syntax + pytest exit codes and writes structured deterministic results.
- **playtester**: exploratory black-box runner for game-like apps using repeated `python <script> --actions ... --exit` calls, bounded by step limit, with compact bug reports in `/workspace/artifacts/playtest.summary.json` and optional `/workspace/artifacts/playtest.log.md`.
- **product_reviewer**: final semantic check after deterministic and creative testing.

## Deterministic vs creative testing

### Deterministic static testing
- strict and reproducible
- syntax checks on relevant files
- pytest execution for fixed scenario checks
- pass/fail based on tool exit codes/output contracts (never model override)

### Creative exploratory play-testing
- black-box interaction loop
- reruns game each step with accumulated `--actions ... --exit`
- parses shown numeric actions, picks next action, tracks visited states
- stops on win, stuck loop, inconsistency, execution error, or step limit

## Artifacts (compact state strategy)

The graph state remains compact and stores only summaries/paths. Larger content is file-backed:

- `/workspace/artifacts/requirements.current.md`
- `/workspace/artifacts/change_scope.json`
- `/workspace/artifacts/implementation.summary.json`
- `/workspace/artifacts/test.summary.json`
- `/workspace/artifacts/playtest.summary.json`
- `/workspace/artifacts/review.summary.json`
- optional `/workspace/artifacts/playtest.log.md`

This keeps prompts small for limited context windows.

## Logging

Workflow logs are optimized for `docker logs` readability:

- node start/end
- routing decisions
- deterministic test outcomes (including pytest exit code)
- concise playtester step logs (`step`, selected action sequence, stuck/win status)
- final status

## Run

```bash
python -m app.workflow "Build or update my CLI app..."
```

Then inspect artifacts under `/workspace/artifacts/` and logs for routing/test/playtest behavior.
