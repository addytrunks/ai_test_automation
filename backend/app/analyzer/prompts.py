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
    "You understand BOLA/IDOR, broken authentication, mass assignment, injection, "
    "and input validation issues.\n\n"
    "For security scenario types (bola, auth_bypass, injection, mass_assignment): "
    "if the API returned a MORE permissive response than expected (e.g. expected 403 "
    "but got 200), classify likely_cause as a potential security vulnerability, "
    "not a broken test.\n\n"
    "likely_cause should use one of: validation_error, auth_misconfiguration, "
    "test_assertion_too_strict, bola_vulnerability, auth_bypass_vulnerability, "
    "injection_vulnerability, mass_assignment_vulnerability, server_error, unknown.\n\n"
    "Be specific — reference actual values from the request and response."
)


def _truncate_body(body: dict[str, Any] | str | None) -> str:
    """Compact and truncate response body for LLM prompt inclusion."""
    if body is None:
        return "<empty>"
    s = json.dumps(body, separators=(",", ":")) if isinstance(body, dict) else str(body)
    if len(s) > MAX_BODY_CHARS:
        return s[:MAX_BODY_CHARS] + "\n[TRUNCATED]"
    return s


def _format_optional_json(label: str, value: Any) -> str:
    if value is None:
        return f"{label}: <none>"
    return f"{label}:\n{json.dumps(value, indent=2, default=str)}"


def build_failure_prompt(
    *,
    test_name: str,
    test_description: str | None,
    scenario_type: str,
    method: str,
    path: str,
    expected_status: int,
    assertions: list[dict[str, Any]] | None,
    headers: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
    path_params: dict[str, Any] | None = None,
    query_params: dict[str, Any] | None = None,
    response_status: int | None,
    response_body: dict[str, Any] | str | None,
    assertion_results: list[dict[str, Any]] | None,
) -> str:
    """Build a 3-layer failure analysis prompt."""
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

== REQUEST SENT ==
{_format_optional_json("Headers", headers)}
{_format_optional_json("Path Params", path_params)}
{_format_optional_json("Query Params", query_params)}
{_format_optional_json("Body", body)}

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
