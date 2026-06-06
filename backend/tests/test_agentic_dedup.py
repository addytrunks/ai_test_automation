"""Unit tests for agentic loop deduplication helpers."""

from __future__ import annotations

import uuid

from app.agentic.dedup import (
    compute_generation_hash,
    gap_scenario_key,
    infer_scenario_type,
    scenario_is_sufficiently_covered,
    should_skip_new_gap,
)
from app.models import CoverageGap, Test


def _sample_test_row(
    endpoint_id: uuid.UUID,
    scenario_type: str,
    *,
    method: str = "POST",
    path: str = "/users/v1/login",
    body: dict | None = None,
) -> Test:
    return Test(
        test_suite_id=uuid.uuid4(),
        endpoint_id=endpoint_id,
        name="sample",
        scenario_type=scenario_type,
        method=method,
        path=path,
        body=body,
        expected_status=401,
    )


def test_compute_generation_hash_ignores_description_wording():
    ep = uuid.uuid4()
    h1 = compute_generation_hash(
        ep,
        "auth_bypass",
        "POST",
        "/users/v1/login",
        body={"username": "", "password": "x"},
        expected_status=401,
    )
    h2 = compute_generation_hash(
        ep,
        "auth_bypass",
        "POST",
        "/users/v1/login",
        body={"username": "", "password": "x"},
        expected_status=401,
    )
    assert h1 == h2


def test_compute_generation_hash_differs_by_body():
    ep = uuid.uuid4()
    h_empty_user = compute_generation_hash(
        ep,
        "auth_bypass",
        "POST",
        "/users/v1/login",
        body={"username": "", "password": "x"},
        expected_status=401,
    )
    h_empty_pass = compute_generation_hash(
        ep,
        "auth_bypass",
        "POST",
        "/users/v1/login",
        body={"username": "a", "password": ""},
        expected_status=401,
    )
    assert h_empty_user != h_empty_pass


def test_infer_scenario_type_keywords():
    assert infer_scenario_type("Missing BOLA test on user profile") == "bola"
    assert infer_scenario_type("Unauthenticated access without bearer token") == "auth_bypass"
    assert infer_scenario_type("SQL injection via username field") == "injection"
    assert infer_scenario_type("Missing boundary overflow check") == "boundary"
    assert infer_scenario_type("Missing negative validation") == "negative"


def test_scenario_is_sufficiently_covered():
    ep = uuid.uuid4()
    tests = [
        _sample_test_row(ep, "auth_bypass"),
        _sample_test_row(ep, "auth_bypass", body={"username": "a", "password": ""}),
    ]
    assert scenario_is_sufficiently_covered(
        tests, ep, "Missing auth bypass test for login"
    )
    assert not scenario_is_sufficiently_covered(
        tests, ep, "Missing BOLA test for login"
    )


def test_should_skip_new_gap_when_spawned_gap_exists():
    ep = uuid.uuid4()
    tests: list[Test] = []
    existing = [
        CoverageGap(
            test_suite_id=uuid.uuid4(),
            endpoint_id=ep,
            run_id=uuid.uuid4(),
            scenario_description="Missing auth bypass on login",
            severity="high",
            spawned_test_id=uuid.uuid4(),
        )
    ]
    assert should_skip_new_gap(
        tests, existing, ep, "Unauthenticated login attempt should fail"
    )


def test_should_skip_new_gap_when_pending_duplicate():
    ep = uuid.uuid4()
    tests: list[Test] = []
    existing = [
        CoverageGap(
            test_suite_id=uuid.uuid4(),
            endpoint_id=ep,
            run_id=uuid.uuid4(),
            scenario_description="Missing BOLA on GET user",
            severity="high",
        )
    ]
    assert should_skip_new_gap(tests, existing, ep, "IDOR on user profile endpoint")


def test_gap_scenario_key_normalizes_similar_descriptions():
    ep = uuid.uuid4()
    assert gap_scenario_key(ep, "Missing BOLA test") == gap_scenario_key(
        ep, "User B accesses User A resource (IDOR)"
    )
