"""
Test generation service.

Orchestrates the LLM-driven test generation process:
1. Converts endpoint ORM objects into prompt-friendly dicts
2. Calls the LLM via generate_structured()
3. Validates the generated tests against the endpoint
4. Persists valid tests to the database
"""

from __future__ import annotations

import logging
import re
import uuid

from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.generator.prompts import build_generation_prompt
from app.generator.schemas import TestListResult, TestSuiteCreate
from app.llm.client import generate_structured
from app.models import Endpoint, Test, TestSuite

logger = logging.getLogger(__name__)

# System prompt with explicit schema contract so the model knows
# exactly what JSON structure and assertion types are valid.
SYSTEM_PROMPT = (
    "You are an expert API security and QA engineer. Generate test cases as a JSON object "
    "with a 'tests' array. Each test must include: name (string), description (string), "
    "scenario_type (string), expected_status (int), assertions (array of objects with 'type' "
    "and 'expected' fields). Optional fields: path_params, query_params, headers, body. "
    "Valid assertion types: status_eq, status_in, body_contains, body_not_contains, "
    "json_path, header_eq, response_time_lt. Return ONLY the JSON object, no markdown, "
    "no explanation and no preamble."
)


async def _generate_for_endpoint(
    db: AsyncSession,
    suite_id: uuid.UUID,
    endpoint: Endpoint,
    scenarios: list[str],
) -> int:
    """
    Generate tests for a single endpoint and save them.

    Returns the number of valid tests saved.
    """
    # Convert endpoint ORM object to dict for the prompt
    ep_dict = {
        "method": endpoint.method,
        "path": endpoint.path,
        "summary": endpoint.summary,
        "parameters": endpoint.parameters,
        "request_body": endpoint.request_body,
        "responses": endpoint.responses,
    }

    prompt = build_generation_prompt(ep_dict, scenarios)

    # Call LLM with structured output
    # temperature=0.3: low enough for deterministic, spec-faithful output,
    # high enough to allow variation across scenario types. Tunable in Week 7 evaluation.
    result = await generate_structured(
        prompt=prompt,
        response_model=TestListResult,
        system_prompt=SYSTEM_PROMPT,
        temperature=0.3,
    )

    # Extract path template variables (e.g. "/users/{id}" -> {"id"})
    path_vars = set(re.findall(r"\{(\w+)\}", endpoint.path))

    # Validate tests against endpoint
    valid_tests = []
    for t_data in result.tests:
        # If the endpoint path has template variables, verify the test provides
        # path_params with keys that actually match those variables
        if path_vars and not path_vars.issubset(set(t_data.path_params or {})):
            logger.warning(
                "Skipping test '%s': path vars %s not fully covered by path_params %s",
                t_data.name,
                path_vars,
                t_data.path_params,
            )
            continue
        valid_tests.append(t_data)

    # Persist valid tests
    for t_data in valid_tests:
        test_obj = Test(
            test_suite_id=suite_id,
            endpoint_id=endpoint.id,
            name=t_data.name,
            description=t_data.description,
            scenario_type=t_data.scenario_type,
            method=endpoint.method,
            path=endpoint.path,
            path_params=t_data.path_params,
            query_params=t_data.query_params,
            headers=t_data.headers,
            body=t_data.body,
            expected_status=t_data.expected_status,
            assertions=[a.model_dump(exclude_none=True) for a in t_data.assertions],
        )
        db.add(test_obj)

    return len(valid_tests)


async def generate_test_suite_task(
    suite_id: uuid.UUID,
    endpoint_ids: list[uuid.UUID],
    scenarios: list[str],
) -> None:
    """
    Background task entry point for test generation.

    Creates its own DB session (since BackgroundTasks run outside
    the request lifecycle) and processes each endpoint sequentially.
    Each endpoint is committed independently so a single LLM failure
    doesn't lose tests already generated for previous endpoints.
    """
    from app.db import get_sessionmaker

    session_factory = get_sessionmaker()

    async with session_factory() as db:
        suite = await db.scalar(select(TestSuite).where(TestSuite.id == suite_id))
        if not suite:
            logger.error("Suite %s not found, aborting generation", suite_id)
            return

        suite.status = "generating"
        await db.commit()

        total_tests = 0
        for ep_id in endpoint_ids:
            endpoint = await db.scalar(select(Endpoint).where(Endpoint.id == ep_id))
            if not endpoint:
                logger.warning("Endpoint %s not found, skipping", ep_id)
                continue
            try:
                count = await _generate_for_endpoint(db, suite_id, endpoint, scenarios)
                await db.commit()  # persist this endpoint's tests before moving on
                total_tests += count
                logger.info(
                    "Generated %d tests for %s %s", count, endpoint.method, endpoint.path
                )
            except Exception:
                logger.exception(
                    "Failed to generate tests for endpoint %s %s, skipping",
                    endpoint.method,
                    endpoint.path,
                )
                await db.rollback()
                continue

        # Re-fetch suite after potential rollbacks
        suite = await db.scalar(select(TestSuite).where(TestSuite.id == suite_id))
        if suite:
            suite.status = "ready"
            logger.info(
                "Suite %s generation complete: %d tests total", suite_id, total_tests
            )
            await db.commit()


async def create_test_suite(
    db: AsyncSession,
    project_id: uuid.UUID,
    payload: TestSuiteCreate,
    background_tasks: BackgroundTasks,
) -> TestSuite:
    """Create a test suite record and kick off background generation."""
    suite = TestSuite(
        project_id=project_id,
        spec_id=payload.spec_id,
        name=payload.name,
        status="pending",
    )
    db.add(suite)
    await db.commit()
    await db.refresh(suite)

    # Enqueue background generation
    background_tasks.add_task(
        generate_test_suite_task, suite.id, payload.endpoint_ids, payload.scenarios
    )

    return suite


async def get_test_suites(db: AsyncSession, project_id: uuid.UUID) -> list[TestSuite]:
    """List all test suites for a project."""
    result = await db.execute(
        select(TestSuite)
        .where(TestSuite.project_id == project_id)
        .order_by(TestSuite.created_at.desc())
    )
    return list(result.scalars().all())


async def get_test_suite(db: AsyncSession, suite_id: uuid.UUID) -> TestSuite | None:
    """Get a single test suite by ID."""
    result = await db.execute(select(TestSuite).where(TestSuite.id == suite_id))
    return result.scalar_one_or_none()


async def get_tests(db: AsyncSession, suite_id: uuid.UUID) -> list[Test]:
    """List all tests in a test suite."""
    result = await db.execute(
        select(Test)
        .where(Test.test_suite_id == suite_id)
        .order_by(Test.scenario_type, Test.name)
    )
    return list(result.scalars().all())
