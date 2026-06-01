"""Assertion evaluation engine for test runner.

Supports all 7 assertion types from the generator schema:
  status_eq, status_in, json_path, body_contains,
  body_not_contains, header_eq, response_time_lt
"""

from __future__ import annotations

import logging
from typing import Any

from jsonpath_ng import parse as jp_parse  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


def evaluate_assertions(
    assertions: list[dict[str, Any]],
    response_status: int,
    response_headers: dict[str, str],
    response_body: dict[str, Any] | str,
    duration_ms: int,
) -> tuple[bool, list[dict[str, Any]]]:
    """Evaluate a list of assertions against an HTTP response.

    Returns (all_passed, results) where results is a list of dicts
    with keys: assertion, passed, actual, error.
    """
    results: list[dict[str, Any]] = []
    all_passed = True

    for assertion in assertions:
        type_ = assertion.get("type")
        passed = False
        actual: Any = None
        error: str | None = None

        try:
            if type_ == "status_eq":
                expected = assertion.get("expected")
                actual = response_status
                passed = actual == expected

            elif type_ == "status_in":
                expected = assertion.get("expected")  # list of ints
                actual = response_status
                passed = actual in (expected or [])

            elif type_ == "json_path":
                if not isinstance(response_body, dict):
                    error = "Response body is not JSON"
                else:
                    target = assertion.get("target")
                    op = assertion.get("op")
                    expected = assertion.get("expected")

                    jsonpath_expr = jp_parse(target)
                    matches = jsonpath_expr.find(response_body)

                    if op == "exists":
                        passed = len(matches) > 0
                        actual = "exists" if passed else "not found"
                    elif op == "eq":
                        actual = matches[0].value if matches else None
                        passed = actual == expected

            elif type_ == "body_contains":
                expected = assertion.get("expected")
                actual_str = str(response_body)
                passed = str(expected) in actual_str
                actual = "contained" if passed else "not contained"

            elif type_ == "body_not_contains":
                expected = assertion.get("expected")
                actual_str = str(response_body)
                passed = str(expected) not in actual_str
                actual = "not contained" if passed else "contained"

            elif type_ == "header_eq":
                target = assertion.get("target", "").lower()
                expected = assertion.get("expected")
                # Normalize header keys to lowercase for case-insensitive lookup
                lower_headers = {k.lower(): v for k, v in response_headers.items()}
                actual = lower_headers.get(target)
                passed = actual == expected

            elif type_ == "response_time_lt":
                expected = assertion.get("expected")
                actual = duration_ms
                passed = actual < expected

            else:
                error = f"Unknown assertion type: {type_}"

        except Exception as e:
            error = str(e)

        if not passed:
            all_passed = False

        results.append(
            {
                "assertion": assertion,
                "passed": passed,
                "actual": actual,
                "error": error,
            }
        )

    return all_passed, results
