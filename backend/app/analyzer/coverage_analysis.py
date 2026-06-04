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

from app.llm.client import generate_structured_with_usage
from app.models import CoverageGap, Endpoint, Test, TestResult, TestSuite

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
HIGH and MEDIUM severity gaps."""


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

    # (a) Fetch all endpoints for this spec
    ep_result = await db.execute(
        select(Endpoint).where(Endpoint.spec_id == suite.spec_id)
    )
    endpoints_list = ep_result.scalars().all()

    # (b) Fetch all Test records for the suite, grouped by endpoint
    test_result = await db.execute(
        select(Test).where(Test.test_suite_id == suite_id)
    )
    tests = test_result.scalars().all()
    tests_by_endpoint: dict[uuid.UUID, list[Test]] = {}
    for t in tests:
        tests_by_endpoint.setdefault(t.endpoint_id, []).append(t)

    # Filter endpoints to only those targeted by tests in the suite.
    # This prevents resource cross-contamination (e.g. users suite generating books tests).
    in_scope_endpoint_ids = set(tests_by_endpoint.keys())
    endpoints_list = [ep for ep in endpoints_list if ep.id in in_scope_endpoint_ids]

    # Build path -> endpoint lookup for O(1) matching
    endpoints_by_path: dict[str, Endpoint] = {ep.path: ep for ep in endpoints_list}
    valid_paths = list(endpoints_by_path.keys())

    # (c) Fetch all TestResult records for the given run_id
    tr_result = await db.execute(
        select(TestResult).where(TestResult.run_id == run_id)
    )
    test_results = tr_result.scalars().all()
    results_by_test_id = {tr.test_id: tr for tr in test_results}

    # Build a structured summary for the LLM
    endpoint_summaries = []
    for ep in endpoints_list:
        ep_tests = tests_by_endpoint.get(ep.id, [])
        test_details = []
        for t in ep_tests:
            tr = results_by_test_id.get(t.id)
            test_details.append({
                "name": t.name,
                "description": t.description,
                "scenario_type": t.scenario_type,
                "status": tr.status if tr else "not_run",
                "assertion_results": tr.assertion_results if tr else None,
            })
        endpoint_summaries.append({
            "method": ep.method,
            "path": ep.path,
            "summary": ep.summary,
            "test_count": len(ep_tests),
            "tests": test_details,
        })

    prompt = f"""Analyze the test coverage for this API suite based on ACTUAL test results.

Endpoints and their test outcomes:
{json.dumps(endpoint_summaries, indent=2, default=str)}

For each endpoint, consider:
1. Are there endpoints with ZERO tests? (high severity)
2. Which tests FAILED - do the failures indicate missing negative/security tests?
3. Are there untested scenario types (auth_bypass, BOLA/IDOR, boundary, injection)?
4. Are there parameter combinations or edge cases not covered?

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

        gaps = []
        for g in result.gaps:
            matched_ep = endpoints_by_path.get(g.endpoint_path)
            if not matched_ep:
                logger.warning(
                    "Gap endpoint_path '%s' not found in spec, skipping",
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

        await db.commit()
        logger.info(
            "Found %d coverage gaps for suite %s (tokens: %d)",
            len(gaps), suite_id, tokens_used,
        )
        return gaps, tokens_used
    except Exception:
        logger.exception("Coverage gap analysis failed for suite %s", suite_id)
        await db.rollback()
        return [], 0
