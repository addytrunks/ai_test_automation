"""Deduplication helpers for the agentic loop.

Centralizes generation hashing, scenario inference from gap descriptions,
and logic for skipping gaps that are already covered by existing tests.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from app.models import CoverageGap, Test

# Minimum tests per (endpoint, scenario) before we stop generating for that gap.
MIN_TESTS_PER_SCENARIO = 2


def infer_scenario_type(text: str) -> str:
    """Map a gap description to a scenario type for coverage matching."""
    desc = text.lower()
    if "bola" in desc or "idor" in desc:
        return "bola"
    if "auth" in desc or "bypass" in desc or "unauthenticated" in desc:
        return "auth_bypass"
    if "injection" in desc or "sqli" in desc or "xss" in desc or "nosql" in desc:
        return "injection"
    if "boundary" in desc or "edge" in desc or "overflow" in desc:
        return "boundary"
    return "negative"


def _normalize_mapping(value: dict[str, Any] | None) -> str:
    if not value:
        return ""
    return json.dumps(value, sort_keys=True, default=str)


def compute_generation_hash(
    endpoint_id: str | uuid.UUID,
    scenario_type: str,
    method: str,
    path: str,
    *,
    path_params: dict[str, Any] | None = None,
    query_params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
    expected_status: int | None = None,
    name: str | None = None,
) -> str:
    """Compute SHA-256 dedup hash from structural test fields.

    Uses method, path, params, body, and expected status so semantically
    identical tests with different names/descriptions still deduplicate.
    Pass ``name`` only when importing baseline tests that share payloads
    but represent distinct cases (e.g. invalid token vs missing auth).
    """
    raw = "|".join(
        [
            str(endpoint_id),
            scenario_type.strip().lower(),
            method.strip().upper(),
            path.strip(),
            _normalize_mapping(path_params),
            _normalize_mapping(query_params),
            _normalize_mapping(body if isinstance(body, dict) else None),
            str(expected_status if expected_status is not None else ""),
            (name or "").strip().lower(),
        ]
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def compute_generation_hash_from_test(test: Test) -> str:
    """Compute hash for an existing Test row."""
    body = test.body if isinstance(test.body, dict) else None
    return compute_generation_hash(
        test.endpoint_id,
        test.scenario_type,
        test.method,
        test.path,
        path_params=test.path_params,
        query_params=test.query_params,
        body=body,
        expected_status=test.expected_status,
    )


def count_scenario_tests(
    tests: list[Test], endpoint_id: uuid.UUID, scenario_type: str
) -> int:
    return sum(
        1
        for t in tests
        if t.endpoint_id == endpoint_id and t.scenario_type == scenario_type
    )


def scenario_is_sufficiently_covered(
    tests: list[Test],
    endpoint_id: uuid.UUID,
    scenario_description: str,
    *,
    min_tests: int = MIN_TESTS_PER_SCENARIO,
) -> bool:
    """Return True when the suite already has enough tests for this gap's scenario."""
    scenario = infer_scenario_type(scenario_description)
    return count_scenario_tests(tests, endpoint_id, scenario) >= min_tests


def gap_scenario_key(endpoint_id: uuid.UUID, scenario_description: str) -> tuple[str, str]:
    return (str(endpoint_id), infer_scenario_type(scenario_description))


def gap_already_tracked(
    existing_gaps: list[CoverageGap],
    endpoint_id: uuid.UUID,
    scenario_description: str,
) -> bool:
    """True if this endpoint+scenario already has a gap with a spawned test."""
    key = gap_scenario_key(endpoint_id, scenario_description)
    for gap in existing_gaps:
        if gap_scenario_key(gap.endpoint_id, gap.scenario_description) != key:
            continue
        if gap.spawned_test_id is not None:
            return True
    return False


def should_skip_new_gap(
    tests: list[Test],
    existing_gaps: list[CoverageGap],
    endpoint_id: uuid.UUID,
    scenario_description: str,
) -> bool:
    """Decide whether a newly identified gap should be persisted."""
    if scenario_is_sufficiently_covered(tests, endpoint_id, scenario_description):
        return True
    if gap_already_tracked(existing_gaps, endpoint_id, scenario_description):
        return True
    key = gap_scenario_key(endpoint_id, scenario_description)
    pending_keys = {
        gap_scenario_key(g.endpoint_id, g.scenario_description)
        for g in existing_gaps
        if g.spawned_test_id is None
    }
    return key in pending_keys
