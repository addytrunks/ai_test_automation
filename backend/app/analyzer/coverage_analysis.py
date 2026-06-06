"""Coverage gap analysis service.

Analyzes the results of a test run against the full API spec to identify
untested scenarios — particularly security-critical ones like BOLA/IDOR
and auth bypass. Returns persisted CoverageGap records and the token
count consumed by the LLM call.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agentic.dedup import infer_scenario_type, should_skip_new_gap
from app.llm.client import generate_structured_with_usage
from app.models import CoverageGap, Endpoint, Run, Test, TestResult, TestSuite

logger = logging.getLogger(__name__)


class GapSchema(BaseModel):
    endpoint_path: str
    scenario_description: str
    severity: Literal["low", "medium", "high"]


class GapListSchema(BaseModel):
    gaps: list[GapSchema]


COVERAGE_ANALYSIS_SYSTEM_PROMPT = """\
You are a security-focused API test coverage analyst. Given a set of API \
endpoints and their actual test results, identify gaps in test coverage. \
Focus on security-critical scenarios: BOLA/IDOR, authentication bypass, \
privilege escalation, injection, and boundary conditions. Return only \
HIGH and MEDIUM severity gaps.

Rules:
- Do NOT report gaps for scenario types already listed under scenario_types_covered.
- If a test has status passed/failed/error, that scenario IS covered — do not \
ask for duplicate tests of the same scenario type on the same endpoint.
- A FAILED test means the scenario was executed; only report a gap if a \
DIFFERENT scenario type is still missing (not more tests of the same type).
- Tests with result_source prior_run were not re-executed this iteration but \
have valid results — treat them as covered. Never report gaps solely because \
a test was not in the current run batch."""


async def _load_latest_results_by_test_id(
    db: AsyncSession, suite_id: uuid.UUID
) -> dict[uuid.UUID, TestResult]:
    """Most recent TestResult per test across all runs in the suite."""
    tr_result = await db.execute(
        select(TestResult)
        .join(Run, TestResult.run_id == Run.id)
        .where(Run.test_suite_id == suite_id)
        .order_by(TestResult.created_at.desc())
    )
    latest: dict[uuid.UUID, TestResult] = {}
    for tr in tr_result.scalars().all():
        if tr.test_id not in latest:
            latest[tr.test_id] = tr
    return latest


async def analyze_coverage_gaps(
    db: AsyncSession, suite_id: uuid.UUID, run_id: uuid.UUID
) -> tuple[list[CoverageGap], int]:
    """Analyze coverage gaps using actual test definitions and run results.

    Args:
        db: Database session.
        suite_id: The test suite to analyze.
        run_id: The specific run whose results inform the gap analysis.

    Returns:
        A tuple of (list_of_persisted_gaps, tokens_used).
    """
    suite = await db.get(TestSuite, suite_id)
    if not suite:
        return [], 0

    ep_result = await db.execute(
        select(Endpoint).where(Endpoint.spec_id == suite.spec_id)
    )
    endpoints_list = ep_result.scalars().all()

    test_result = await db.execute(
        select(Test).where(Test.test_suite_id == suite_id)
    )
    tests = list(test_result.scalars().all())
    tests_by_endpoint: dict[uuid.UUID, list[Test]] = {}
    for t in tests:
        tests_by_endpoint.setdefault(t.endpoint_id, []).append(t)

    in_scope_endpoint_ids = set(tests_by_endpoint.keys())
    endpoints_list = [ep for ep in endpoints_list if ep.id in in_scope_endpoint_ids]

    endpoints_by_path: dict[str, Endpoint] = {ep.path: ep for ep in endpoints_list}
    valid_paths = list(endpoints_by_path.keys())

    current_run_results = await db.execute(
        select(TestResult).where(TestResult.run_id == run_id)
    )
    results_by_test_id_current = {
        tr.test_id: tr for tr in current_run_results.scalars().all()
    }
    latest_results_by_test_id = await _load_latest_results_by_test_id(db, suite_id)

    existing_gaps_result = await db.execute(
        select(CoverageGap).where(CoverageGap.test_suite_id == suite_id)
    )
    existing_gaps = list(existing_gaps_result.scalars().all())

    endpoint_summaries = []
    for ep in endpoints_list:
        ep_tests = tests_by_endpoint.get(ep.id, [])
        scenario_types_covered = sorted({t.scenario_type for t in ep_tests})
        test_details = []
        for t in ep_tests:
            current_tr = results_by_test_id_current.get(t.id)
            if current_tr:
                tr = current_tr
                result_source = "current_run"
            elif t.id in latest_results_by_test_id:
                tr = latest_results_by_test_id[t.id]
                result_source = "prior_run"
            else:
                tr = None
                result_source = "never_run"

            test_details.append({
                "name": t.name,
                "description": t.description,
                "scenario_type": t.scenario_type,
                "status": tr.status if tr else "never_run",
                "result_source": result_source,
                "assertion_results": tr.assertion_results if tr else None,
            })
        endpoint_summaries.append({
            "method": ep.method,
            "path": ep.path,
            "summary": ep.summary,
            "test_count": len(ep_tests),
            "scenario_types_covered": scenario_types_covered,
            "tests": test_details,
        })

    prompt = f"""Analyze the test coverage for this API suite based on ACTUAL test results.

Endpoints and their test outcomes:
{json.dumps(endpoint_summaries, indent=2, default=str)}

For each endpoint, consider:
1. Are there endpoints with ZERO tests? (high severity)
2. Which scenario types in auth_bypass, bola, injection, boundary are NOT in scenario_types_covered?
3. Do NOT re-report scenarios that already have tests (even if those tests failed).

IMPORTANT: endpoint_path values in your response MUST be chosen EXACTLY from this list:
{json.dumps(valid_paths)}

Return only HIGH and MEDIUM severity gaps. Prioritize BOLA/IDOR and auth_bypass."""

    try:
        result, tokens_used = await generate_structured_with_usage(
            prompt=prompt,
            response_model=GapListSchema,
            system_prompt=COVERAGE_ANALYSIS_SYSTEM_PROMPT,
            temperature=0.3,
        )

        gaps: list[CoverageGap] = []
        skipped = 0
        for g in result.gaps:
            matched_ep = endpoints_by_path.get(g.endpoint_path)
            if not matched_ep:
                logger.warning(
                    "Gap endpoint_path '%s' not found in spec, skipping",
                    g.endpoint_path,
                )
                continue

            if should_skip_new_gap(tests, existing_gaps, matched_ep.id, g.scenario_description):
                skipped += 1
                logger.info(
                    "Skipping duplicate gap [%s] %s on %s",
                    infer_scenario_type(g.scenario_description),
                    g.scenario_description[:60],
                    g.endpoint_path,
                )
                continue

            gap = CoverageGap(
                test_suite_id=suite_id,
                endpoint_id=matched_ep.id,
                run_id=run_id,
                scenario_description=g.scenario_description,
                severity=g.severity.lower(),
            )
            db.add(gap)
            gaps.append(gap)
            existing_gaps.append(gap)

        await db.commit()
        logger.info(
            "Found %d coverage gaps for suite %s (%d skipped as already covered, tokens: %d)",
            len(gaps),
            suite_id,
            skipped,
            tokens_used,
        )
        return gaps, tokens_used
    except Exception:
        logger.exception("Coverage gap analysis failed for suite %s", suite_id)
        await db.rollback()
        return [], 0
