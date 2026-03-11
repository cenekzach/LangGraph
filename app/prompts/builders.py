from __future__ import annotations

import textwrap


def shrink(text: str, limit: int = 1200) -> str:
    clean = (text or "").strip()
    if len(clean) <= limit:
        return clean
    return clean[:limit] + "\n...[truncated]"


def requirements_prompt(user_request: str, feedback: str) -> str:
    return textwrap.dedent(
        f"""
        Write concise requirements in Markdown using these sections exactly:
        Title, Goal, Functional requirements, Non-goals, Inputs / outputs, Constraints, Edge cases, Acceptance criteria.

        Keep it concrete and testable. 180-320 words.

        User request:
        {shrink(user_request, 900)}

        Reviewer feedback to address:
        {shrink(feedback or 'none', 500)}
        """
    ).strip()


def requirements_review_prompt(requirements_md: str) -> str:
    return textwrap.dedent(
        f"""
        Review the requirements markdown for clarity, consistency, and testability.
        Return strict JSON with keys:
        requirements_ok (boolean), issues (array of short strings), rewrite_instructions (string), summary (string).

        Requirements markdown:
        {shrink(requirements_md, 2500)}
        """
    ).strip()


def implementation_prompt(user_request: str, requirements_summary: str, feedback: str) -> str:
    return textwrap.dedent(
        f"""
        Produce implementation plan JSON only with keys:
        source_files: array of objects {{path, content}},
        implementation_summary: short string.

        Keep scope minimal and deterministic. Python only.

        User request: {shrink(user_request, 500)}
        Requirements summary: {shrink(requirements_summary, 1200)}
        Latest feedback: {shrink(feedback or 'none', 700)}
        """
    ).strip()


def tests_prompt(requirements_summary: str, implementation_summary: str, source_paths: list[str]) -> str:
    src = ", ".join(source_paths[:8])
    return textwrap.dedent(
        f"""
        Generate test assets JSON only with keys:
        test_files: array of objects {{path, content}},
        test_summary: short string.

        Write compact pytest-style tests.
        Requirements summary: {shrink(requirements_summary, 1200)}
        Implementation summary: {shrink(implementation_summary, 600)}
        Source paths: {src}
        """
    ).strip()


def product_review_prompt(requirements_summary: str, implementation_summary: str, test_summary: str) -> str:
    return textwrap.dedent(
        f"""
        Decide if the product aligns with requirements intent.
        Return strict JSON with keys:
        product_review_ok (boolean),
        route (one of "end", "implementor", "requirements_author"),
        summary (string).

        Requirements summary: {shrink(requirements_summary, 1200)}
        Implementation summary: {shrink(implementation_summary, 900)}
        Test summary: {shrink(test_summary, 600)}
        """
    ).strip()
