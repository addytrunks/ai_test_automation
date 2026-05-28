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

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.generator.prompts import build_generation_prompt
from app.generator.schemas import TestListResult, TestSuiteCreate
from app.llm.client import generate_structured
from app.models import Endpoint, Test, TestSuite

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Endpoint-level guardrails (mirrors frontend SCENARIO_RULES)
# ---------------------------------------------------------------------------

def _ep_has_path_params(ep: Endpoint) -> bool:
    """True if the endpoint path contains template variables like {id}."""
    return bool(re.search(r"\{[^}]+\}", ep.path))


def _ep_has_request_body(ep: Endpoint) -> bool:
    """True if the endpoint accepts a JSON request body (POST/PUT/PATCH)."""
    return bool(ep.request_body) and ep.method.lower() in ("post", "put", "patch")


def _ep_has_inputs(ep: Endpoint) -> bool:
    """True if the endpoint has parameters or a request body."""
    return _ep_has_request_body(ep) or bool(ep.parameters)


def _ep_has_auth(ep: Endpoint) -> bool:
    """True if the endpoint has a security requirement."""
    if ep.security and len(ep.security) > 0:
        return True
    for p in (ep.parameters or []):
        if isinstance(p, dict) and p.get("name", "").lower() == "authorization":
            return True
    return False


def _filter_scenarios_for_endpoint(ep: Endpoint, scenarios: list[str]) -> list[str]:
    """Remove scenarios that are structurally impossible for this endpoint.

    This is the backend counterpart of the frontend SCENARIO_RULES guardrails.
    Prevents the LLM from receiving prompts for impossible scenario/endpoint
    combinations (e.g. BOLA on a public endpoint with no path params).
    """
    filtered = []
    for s in scenarios:
        if s == "bola" and (not _ep_has_path_params(ep) or not _ep_has_auth(ep)):
            logger.info("  ↳ Stripped '%s' — endpoint lacks path params or auth", s)
            continue
        if s == "auth_bypass" and not _ep_has_auth(ep):
            logger.info("  ↳ Stripped '%s' — endpoint has no security requirement", s)
            continue
        if s == "mass_assignment" and not _ep_has_request_body(ep):
            logger.info("  ↳ Stripped '%s' — endpoint has no request body", s)
            continue
        if s == "injection" and not _ep_has_inputs(ep):
            logger.info("  ↳ Stripped '%s' — endpoint has no injectable inputs", s)
            continue
        if s == "boundary" and not _ep_has_inputs(ep):
            logger.info("  ↳ Stripped '%s' — endpoint has no inputs for boundary testing", s)
            continue
        if s == "positive" and not _ep_has_inputs(ep):
            logger.info("  ↳ Stripped '%s' — endpoint has no documented inputs", s)
            continue
        filtered.append(s)
    return filtered


# System prompt with explicit schema contract so the model knows
# exactly what JSON structure, assertion types, and templating rules are valid.
SYSTEM_PROMPT = (
    "You are an expert API security and QA engineer. Generate test cases as a JSON object "
    "with a 'tests' array. Each test must include: name (string), description (string), "
    "scenario_type (string), expected_status (int), assertions (array of objects with 'type' "
    "and 'expected' fields). Optional fields: path_params, query_params, headers, body, extract.\n\n"

    "Valid scenario_type values: positive, negative, boundary, bola, auth_bypass, injection, "
    "mass_assignment, setup.\n\n"

    "Valid assertion types: status_eq, status_in, body_contains, body_not_contains, "
    "json_path, header_eq, response_time_lt.\n\n"

    "TEMPLATE VARIABLE CONTRACT — THIS IS MANDATORY:\n"
    "Never use hardcoded placeholder strings for tokens, passwords, or dynamic resource IDs. "
    "You MUST use double-brace template variables for any value that will be resolved at runtime. "
    "The only valid token variables are: {{USER_A_TOKEN}}, {{USER_B_TOKEN}}, {{ADMIN_TOKEN}}. "
    "The only valid ID variables are: {{USER_A_ID}}, {{USER_B_ID}}, {{TARGET_RESOURCE_ID}}. "
    "Examples of FORBIDDEN values: 'valid.token.for.user.a', 'Bearer <token>', 'user-b-uuid-1234', "
    "'current-user-uuid', 'some_token'. "
    "If you use any of these forbidden patterns instead of the template variables above, "
    "the output will be rejected.\n\n"

    "SETUP TESTS:\n"
    "When an endpoint requires authentication (i.e. it has a security scheme), you MUST first "
    "generate setup tests that acquire the required tokens. A setup test has "
    "scenario_type='setup' and an 'extract' field: a dict mapping template variable names to "
    "JSONPath expressions that extract them from the response body. "
    "Example: extract: {\"USER_A_TOKEN\": \"$.auth_token\"}. "
    "If the login response does not return the user's ID, you MUST define it using the 'static_context' "
    "field, mapping the template variable (e.g. USER_A_ID) to the static identifier used in the login request. "
    "Example: static_context: {\"USER_A_ID\": \"user1\"}. "
    "Setup tests must appear BEFORE any tests that use the tokens they produce.\n\n"

    "Return ONLY the JSON object, no markdown, no explanation, no preamble."
)


async def _generate_for_endpoint(
    db: AsyncSession,
    suite_id: uuid.UUID,
    endpoint: Endpoint,
    scenarios: list[str],
    auth_endpoint: Endpoint | None = None,
) -> int:
    """
    Generate tests for a single endpoint and save them.

    Returns the number of valid tests saved.
    """
    logger.info(
        "[STEP 1/5] Building prompt for %s %s (scenarios: %s)",
        endpoint.method, endpoint.path, ", ".join(scenarios),
    )

    # Convert endpoint ORM object to dict for the prompt
    ep_dict = {
        "method": endpoint.method,
        "path": endpoint.path,
        "summary": endpoint.summary,
        "parameters": endpoint.parameters,
        "request_body": endpoint.request_body,
        "responses": endpoint.responses,
        "security": endpoint.security,
    }

    auth_ep_dict = None
    if auth_endpoint:
        auth_ep_dict = {
            "method": auth_endpoint.method,
            "path": auth_endpoint.path,
            "summary": auth_endpoint.summary,
            "parameters": auth_endpoint.parameters,
            "request_body": auth_endpoint.request_body,
            "responses": auth_endpoint.responses,
        }
        logger.info(
            "[STEP 1/5] Auth endpoint detected: %s %s — injecting into prompt",
            auth_endpoint.method, auth_endpoint.path,
        )

    prompt = build_generation_prompt(ep_dict, scenarios, auth_ep_dict)

    logger.info(
        "[STEP 2/5] Calling LLM (prompt length: %d chars)...", len(prompt),
    )

    # Call LLM with structured output
    # temperature=0.7: balanced between deterministic output and variation.
    # Tunable in Week 7 evaluation.
    result = await generate_structured(
        prompt=prompt,
        response_model=TestListResult,
        system_prompt=SYSTEM_PROMPT,
        temperature=0.7,
    )

    logger.info(
        "[STEP 3/5] LLM returned %d raw tests. Validating...", len(result.tests),
    )

    # Extract path template variables (e.g. "/users/{id}" -> {"id"})
    path_vars = set(re.findall(r"\{(\w+)\}", endpoint.path))

    # Only allow scenario types that were actually requested (plus "setup" if an auth endpoint is present)
    allowed_scenarios = set(scenarios)
    if auth_endpoint:
        allowed_scenarios.add("setup")

    # Validate tests against endpoint
    valid_tests = []
    for t_data in result.tests:
        # Reject tests belonging to scenarios that were not requested
        if t_data.scenario_type not in allowed_scenarios:
            logger.warning(
                "Skipping test '%s': scenario_type '%s' was not requested (allowed: %s)",
                t_data.name,
                t_data.scenario_type,
                allowed_scenarios,
            )
            continue

        # Setup tests don't need to match path vars — they hit auth endpoints independently
        if t_data.scenario_type == "setup":
            valid_tests.append(t_data)
            continue

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

        # Reject tests that contain forbidden placeholder patterns in headers or body
        serialized = str(t_data.headers or "") + str(t_data.body or "")
        forbidden_patterns = [
            "valid.token", "<token>", "<insert", "user-b-uuid", "current-user-uuid",
            "Bearer some", "Bearer <",
        ]
        if any(p in serialized for p in forbidden_patterns):
            logger.warning(
                "Skipping test '%s': contains forbidden placeholder string in headers/body. "
                "Generator must use {{TEMPLATE_VARS}} instead.",
                t_data.name,
            )
            continue

        valid_tests.append(t_data)

    logger.info(
        "[STEP 4/5] Validation complete: %d/%d tests passed. Persisting to DB...",
        len(valid_tests), len(result.tests),
    )

    # Persist valid tests (truncate name/description to fit DB column limits)
    for t_data in valid_tests:
        test_obj = Test(
            test_suite_id=suite_id,
            endpoint_id=endpoint.id,
            name=(t_data.name or "")[:255],
            description=(t_data.description or "")[:1024],
            scenario_type=t_data.scenario_type,
            method=endpoint.method,
            path=endpoint.path,
            path_params=t_data.path_params,
            query_params=t_data.query_params,
            headers=t_data.headers,
            body=t_data.body,
            expected_status=t_data.expected_status,
            assertions=[a.model_dump(exclude_none=True) for a in t_data.assertions],
            extract=getattr(t_data, "extract", None),
            static_context=getattr(t_data, "static_context", None),
        )
        db.add(test_obj)

    logger.info("[STEP 5/5] Persisted %d tests for %s %s ✓", len(valid_tests), endpoint.method, endpoint.path)
    return len(valid_tests)


async def generate_test_suite_task(
    suite_id: uuid.UUID,
    endpoint_ids: list[uuid.UUID],
    scenarios: list[str],
    auth_endpoint_id: uuid.UUID | None = None,
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

        auth_endpoint = None
        if auth_endpoint_id:
            auth_endpoint = await db.scalar(select(Endpoint).where(Endpoint.id == auth_endpoint_id))

        logger.info(
            "━━━ Suite %s: starting generation for %d endpoints (scenarios: %s) ━━━",
            suite_id, len(endpoint_ids), ", ".join(scenarios),
        )
        if auth_endpoint:
            logger.info("Auth endpoint resolved: %s %s", auth_endpoint.method, auth_endpoint.path)

        total_tests = 0
        for idx, ep_id in enumerate(endpoint_ids, 1):
            endpoint = await db.scalar(select(Endpoint).where(Endpoint.id == ep_id))
            if not endpoint:
                logger.warning("Endpoint %s not found, skipping", ep_id)
                continue
            logger.info(
                "━━━ [Endpoint %d/%d] %s %s ━━━",
                idx, len(endpoint_ids), endpoint.method, endpoint.path,
            )
            try:
                # Filter scenarios to only those that make structural sense for this endpoint
                ep_scenarios = _filter_scenarios_for_endpoint(endpoint, scenarios)
                if not ep_scenarios:
                    logger.info(
                        "  ⊘ All scenarios stripped for %s %s — skipping LLM call entirely",
                        endpoint.method, endpoint.path,
                    )
                    continue
                count = await _generate_for_endpoint(db, suite_id, endpoint, ep_scenarios, auth_endpoint)
                await db.commit()  # persist this endpoint's tests before moving on
                total_tests += count
                logger.info(
                    "✓ Endpoint %d/%d done: %d tests for %s %s",
                    idx, len(endpoint_ids), count, endpoint.method, endpoint.path,
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
    
    # Load all endpoints for this spec to check security requirements and find auth endpoint
    result = await db.execute(select(Endpoint).where(Endpoint.spec_id == payload.spec_id))
    all_endpoints = list(result.scalars().all())
    
    # Identify selected endpoints
    selected_endpoints = [ep for ep in all_endpoints if ep.id in payload.endpoint_ids]
    
    # Check if any selected endpoint requires auth
    requires_auth = False
    for ep in selected_endpoints:
        if ep.security and len(ep.security) > 0:
            requires_auth = True
            break
        for p in (ep.parameters or []):
            if p.get("name") == "Authorization":
                requires_auth = True
                break

    auth_endpoint_id = None
    if requires_auth:
        # Heuristic: find POST endpoints with login/auth/token in path
        candidates = []
        for ep in all_endpoints:
            if ep.method.lower() == "post":
                path_lower = ep.path.lower()
                if any(k in path_lower for k in ["login", "auth", "token", "signin", "sessions"]):
                    candidates.append(ep)
        
        if len(candidates) == 1:
            auth_endpoint_id = candidates[0].id
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Could not auto-detect a unique authentication endpoint (found {len(candidates)} candidates). "
                "Generation of authenticated test suites requires an auth endpoint config. "
                "(Manual UI configuration pending in Week 4)."
            )

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
        generate_test_suite_task, suite.id, payload.endpoint_ids, payload.scenarios, auth_endpoint_id
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
        .order_by(Test.path, Test.method, Test.scenario_type)
    )
    return list(result.scalars().all())


async def delete_test_suite(db: AsyncSession, suite_id: uuid.UUID) -> None:
    """Delete a test suite by ID."""
    suite = await get_test_suite(db, suite_id)
    if suite:
        await db.delete(suite)
        await db.commit()