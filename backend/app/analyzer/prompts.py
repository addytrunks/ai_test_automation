"""Prompt builders for the failure analysis module.

Builds a 3-layer prompt (intent, expected, actual) for the LLM to analyze
why a specific API test failed. Includes response body truncation to
prevent token limit blowups on verbose APIs.
"""

from __future__ import annotations

import json
from typing import Any

MAX_BODY_CHARS = 4000

FAILURE_ANALYSIS_SYSTEM_PROMPT = (
    "You are an expert API security engineer analyzing automated test failures. "
    "You understand common API vulnerabilities including BOLA, broken authentication, "
    "mass assignment, injection, and improper input validation. "
    "Analyze the test failure and provide a clear explanation, root cause, and fix. "
    "Be specific — reference actual values from the response when relevant."
)


def _truncate_body(body: dict[str, Any] | str | None) -> str:
    """Compact and truncate response body for LLM prompt inclusion.

    Compacts JSON dicts (strips whitespace), then caps at MAX_BODY_CHARS.
    Appends [TRUNCATED] marker so the LLM knows context is missing.
    """
    if body is None:
        return "<empty>"
    s = json.dumps(body, separators=(",", ":")) if isinstance(body, dict) else str(body)
    if len(s) > MAX_BODY_CHARS:
        return s[:MAX_BODY_CHARS] + "\n[TRUNCATED]"
    return s


def build_failure_prompt(
    *,
    test_name: str,
    test_description: str | None,
    scenario_type: str,
    method: str,
    path: str,
    expected_status: int,
    assertions: list[dict[str, Any]] | None,
    response_status: int | None,
    response_body: dict[str, Any] | str | None,
    assertion_results: list[dict[str, Any]] | None,
) -> str:
    """Build a 3-layer failure analysis prompt.

    Layer 1 — Intent: what the test was trying to verify.
    Layer 2 — Expected: what the test expected to happen.
    Layer 3 — Actual: what actually happened (status, body).
    """
    failed_assertions = [a for a in (assertion_results or []) if not a.get("passed")]
    all_assertions_str = json.dumps(assertions or [], indent=2)
    failed_str = json.dumps(failed_assertions, indent=2)

    return f"""\
Analyze this API test failure.

== TEST INTENT ==
Name: {test_name}
Description: {test_description or 'N/A'}
Scenario Type: {scenario_type}
Request: {method} {path}

== EXPECTED BEHAVIOR ==
Expected Status: {expected_status}
Assertions Defined:
{all_assertions_str}

== ACTUAL RESPONSE ==
Status Code: {response_status}
Response Body: {_truncate_body(response_body)}

== ASSERTION RESULTS ==
Failed Assertions:
{failed_str}
"""
