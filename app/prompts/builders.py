from __future__ import annotations

import json
import re
import textwrap


def shrink(text: str, limit: int = 1200) -> str:
    clean = (text or "").strip()
    if len(clean) <= limit:
        return clean
    return clean[:limit] + "\n...[truncated]"


def change_planner_prompt(
    original_request: str,
    latest_request: str,
    current_requirements: str,
    prior_feedback: str,
) -> str:
    return textwrap.dedent(
        f"""
        You are the change_planner for an iterative CLI app project.
        Update requirements in place and keep stable sections intact.

        Output plain text with this exact format:
        REQUIREMENTS_MD:
        ```markdown
        <updated markdown requirements>
        ```
        CHANGE_SCOPE_JSON:
        ```json
        {{
          "change_type": "feature|bugfix|refactor|clarification",
          "affected_behaviors": ["..."],
          "likely_affected_files": ["..."],
          "tests_need_updates": true,
          "requirements_changed_materially": true
        }}
        ```

        Make determinism explicit for interactive CLI games: same --actions sequence must produce same output,
        and --exit must print the next prompt and exit.

        Original request:
        {shrink(original_request, 700)}

        Latest user update request:
        {shrink(latest_request, 900)}

        Current requirements markdown:
        {shrink(current_requirements or 'none yet', 2500)}

        Prior feedback:
        {shrink(prior_feedback or 'none', 600)}
        """
    ).strip()


def parse_change_scope(raw: str) -> tuple[str, dict]:
    requirements_md = ""
    scope: dict = {}

    md_match = re.search(r"REQUIREMENTS_MD:\s*```(?:markdown)?\n(.*?)```", raw, re.DOTALL)
    if md_match:
        requirements_md = md_match.group(1).strip()

    json_match = re.search(r"CHANGE_SCOPE_JSON:\s*```(?:json)?\n(.*?)```", raw, re.DOTALL)
    if json_match:
        try:
            scope = json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            scope = {}

    return requirements_md, scope


def requirements_review_prompt(requirements_md: str) -> str:
    return textwrap.dedent(
        f"""
        Review the requirements markdown for clarity, consistency, and testability.
        Return strict JSON with keys:
        requirements_ok (boolean), issues (array of short strings), rewrite_instructions (string), summary (string).

        Verify CLI contract is explicit where relevant: numeric action format, --actions, --exit behavior, deterministic replay.

        Requirements markdown:
        {shrink(requirements_md, 2500)}
        """
    ).strip()


def implementation_prompt(user_request: str, requirements_summary: str, feedback: str, change_scope: str, interface_contract_summary: str = "") -> str:
    return textwrap.dedent(
        f"""
        Produce implementation artifacts as plain text blocks (NO JSON):

        IMPLEMENTATION_SUMMARY: <one short line>
        FILE_PATH: <relative path>
        ```python
        <file content>
        ```

        Repeat FILE_PATH + fenced content per file.
        Keep edits targeted and deterministic. Python only.

        User request: {shrink(user_request, 500)}
        Requirements summary: {shrink(requirements_summary, 1200)}
        Change scope: {shrink(change_scope, 900)}
        Interface contract: {shrink(interface_contract_summary or "none", 700)}
        Latest feedback: {shrink(feedback or 'none', 700)}
        """
    ).strip()


def deterministic_tests_prompt(
    requirements_summary: str,
    implementation_summary: str,
    source_paths: list[str],
    feedback: str,
    interface_contract_summary: str = "",
) -> str:
    src = ", ".join(source_paths[:8])
    return textwrap.dedent(
        f"""
        Generate deterministic test artifacts as plain text blocks (NO JSON):

        TEST_SUMMARY: <one short line>
        FILE_PATH: <relative test path>
        ```python
        <pytest content>
        ```

        Include fixed scenario checks for interactive CLI contracts when relevant:
        prompt format, numeric-only menu contract, --actions replay, --exit semantics, known winning sequence if defined.

        Requirements summary: {shrink(requirements_summary, 1200)}
        Implementation summary: {shrink(implementation_summary, 600)}
        Source paths: {src}
        Latest feedback: {shrink(feedback or 'none', 600)}
        Interface contract: {shrink(interface_contract_summary or "none", 700)}
        """
    ).strip()


def playtester_prompt(requirements_summary: str, play_history: str, latest_output: str) -> str:
    return textwrap.dedent(
        f"""
        You are a creative but bounded CLI playtester.
        Given the game output, pick exactly one next numeric action as JSON {{"next_action": <int>, "reason": "..."}}.
        Prefer unexplored options and avoid loops.

        Requirements summary:
        {shrink(requirements_summary, 900)}

        Play history summary:
        {shrink(play_history, 800)}

        Latest output:
        {shrink(latest_output, 1500)}
        """
    ).strip()


def product_review_prompt(
    requirements_summary: str,
    implementation_summary: str,
    deterministic_test_summary: str,
    playtest_summary: str,
) -> str:
    return textwrap.dedent(
        f"""
        Decide if the product aligns with requirements intent after deterministic testing and exploratory playtesting.
        Return strict JSON with keys:
        product_review_ok (boolean),
        route (one of "end", "implementor", "change_planner"),
        summary (string).

        Requirements summary: {shrink(requirements_summary, 1200)}
        Implementation summary: {shrink(implementation_summary, 900)}
        Deterministic test summary: {shrink(deterministic_test_summary, 800)}
        Playtest summary: {shrink(playtest_summary, 800)}
        """
    ).strip()


# Backwards compatible alias
def tests_prompt(*args, **kwargs):
    return deterministic_tests_prompt(*args, **kwargs)
