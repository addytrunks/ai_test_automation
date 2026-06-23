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
import time
import uuid
from typing import Any

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


def resolve_auth_endpoints(
    all_endpoints: list[Endpoint],
) -> tuple[Endpoint | None, Endpoint | None]:
    """Heuristic: find unique login and optional register endpoints in a spec."""
    login_candidates: list[Endpoint] = []
    register_candidates: list[Endpoint] = []
    for ep in all_endpoints:
        if ep.method.lower() != "post":
            continue
        path_lower = ep.path.lower()
        if any(k in path_lower for k in ["login", "auth", "token", "signin", "sessions"]):
            login_candidates.append(ep)
        if any(k in path_lower for k in ["register", "signup", "sign-up", "create-user"]):
            register_candidates.append(ep)
    auth_endpoint = login_candidates[0] if len(login_candidates) == 1 else None
    register_endpoint = register_candidates[0] if len(register_candidates) == 1 else None
    return auth_endpoint, register_endpoint


def _endpoint_to_prompt_dict(ep: Endpoint) -> dict[str, Any]:
    return {
        "method": ep.method,
        "path": ep.path,
        "summary": ep.summary,
        "parameters": ep.parameters,
        "request_body": ep.request_body,
        "responses": ep.responses,
        "security": getattr(ep, "security", None),
    }


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
        filtered.append(s)
    return filtered


# System prompt with explicit schema contract so the model knows
# exactly what JSON structure, assertion types, and templating rules are valid.
SYSTEM_PROMPT = (
    "You are an expert API security and QA engineer. Return a JSON object with a 'tests' array.\n"
    "Output skeleton: {\"tests\": [{\"name\": \"...\", \"description\": \"...\", "
    "\"scenario_type\": \"...\", \"expected_status\": 200, \"assertions\": [...]}]}\n\n"

    "Required per test: name, description, scenario_type, expected_status, assertions.\n"
    "Optional: method, path, path_params, query_params, headers, body, extract, static_context.\n"
    "Non-setup tests inherit method/path from the target endpoint unless scenario_type is setup.\n\n"

    "Valid scenario_type values: positive, negative, boundary, bola, auth_bypass, injection, "
    "mass_assignment, setup.\n\n"

    "ASSERTION SCHEMA (all assertions require 'type'):\n"
    "- status_eq: {type, expected: int}\n"
    "- status_in: {type, expected: [int, ...]}\n"
    "- json_path: {type, target: string, op: 'exists'|'eq', expected?: any}\n"
    "- body_contains / body_not_contains: {type, expected: string}\n"
    "- header_eq: {type, target: string, expected: string}\n"
    "- response_time_lt: {type, expected: int}  (milliseconds)\n"
    "MANDATORY: every test MUST include at least one status_eq or status_in assertion. "
    "Prefer status assertions over json_path/body assertions unless the spec documents "
    "response body fields. Do NOT assert exact error message text unless the spec defines it.\n\n"

    "TEMPLATE VARIABLE CONTRACT — MANDATORY:\n"
    "Use double-brace variables for runtime-resolved values. "
    "Tokens: {{USER_A_TOKEN}}, {{USER_B_TOKEN}}. "
    "IDs: {{USER_A_ID}}, {{USER_B_ID}}, {{TARGET_RESOURCE_ID}}.\n"
    "Authorization headers MUST use the Bearer prefix: "
    "{\"Authorization\": \"Bearer {{USER_A_TOKEN}}\"}.\n"
    "ID variable selection: USER_B_ID when the path param is a user identifier; "
    "TARGET_RESOURCE_ID when the path param is an object/resource ID (book, order, etc.).\n"
    "FORBIDDEN: 'valid.token.for.user.a', 'Bearer <token>', hardcoded UUIDs, 'some_token'.\n\n"

    "AUTH BYPASS — distinguish missing vs invalid credentials:\n"
    "- Missing auth test: omit Authorization header entirely (or headers: {}).\n"
    "- Invalid token test: MUST include Authorization with a malformed value "
    "(e.g. \"Bearer invalid_token_xyz\"). Never omit the header when testing invalid tokens.\n\n"

    "SETUP TESTS:\n"
    "1. method/path must point to registration or login endpoints, NOT the target endpoint.\n"
    "2. Register setup BEFORE login setup when a registration endpoint exists.\n"
    "3. Login setup must include extract mapping tokens from the response "
    "(read the token field name from the auth endpoint responses in the prompt).\n"
    "4. Register setup should include static_context for USER_A_ID / USER_B_ID.\n"
    "5. Setup tests must appear before tests that consume their tokens.\n\n"

    "Return ONLY the JSON object. No markdown, no explanation."
)


async def _generate_for_endpoint(
    db: AsyncSession,
    suite_id: uuid.UUID,
    endpoint: Endpoint,
    scenarios: list[str],
    auth_endpoint: Endpoint | None = None,
    register_endpoint: Endpoint | None = None,
    include_setup: bool = False,
) -> int:
    """
    Generate tests for a single endpoint and save them.

    Returns the number of valid tests saved.
    """
    logger.info(
        "[STEP 1/5] Building prompt for %s %s (scenarios: %s)",
        endpoint.method, endpoint.path, ", ".join(scenarios),
    )

    ep_dict = _endpoint_to_prompt_dict(endpoint)

    auth_ep_dict = None
    if auth_endpoint:
        auth_ep_dict = _endpoint_to_prompt_dict(auth_endpoint)
        logger.info(
            "[STEP 1/5] Auth endpoint detected: %s %s — injecting into prompt",
            auth_endpoint.method, auth_endpoint.path,
        )

    reg_ep_dict = None
    if register_endpoint:
        reg_ep_dict = _endpoint_to_prompt_dict(register_endpoint)
        logger.info(
            "[STEP 1/5] Register endpoint detected: %s %s — injecting into prompt",
            register_endpoint.method, register_endpoint.path,
        )

    prompt = build_generation_prompt(
        ep_dict, scenarios, auth_ep_dict, reg_ep_dict, include_setup
    )

    logger.info(
        "[STEP 2/5] Calling LLM (prompt length: %d chars)...", len(prompt),
    )

    # Call LLM with structured output
    # temperature=0.4: balanced between deterministic output and variation.
    # Tunable in Week 7 evaluation.
    start_time = time.time()
    result = await generate_structured(
        prompt=prompt,
        response_model=TestListResult,
        system_prompt=SYSTEM_PROMPT,
        temperature=0.4,
    )
    generation_time = time.time() - start_time
    
    # Log the generation time
    with open("../metrics_log.txt", "a") as f:  # noqa: ASYNC230
        f.write(f"Generation Time (Endpoint {endpoint.method} {endpoint.path}, baseline): {generation_time:.2f} seconds\n")

    logger.info(
        "[STEP 3/5] LLM returned %d raw tests. Validating...", len(result.tests),
    )

    # Extract path template variables (e.g. "/users/{id}" -> {"id"})
    path_vars = set(re.findall(r"\{(\w+)\}", endpoint.path))

    # Only allow scenario types that were actually requested
    allowed_scenarios = set(scenarios)
    if include_setup:
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

        has_status_assertion = any(
            a.type in ("status_eq", "status_in") for a in t_data.assertions
        )
        if not has_status_assertion:
            logger.warning(
                "Skipping test '%s': missing required status_eq or status_in assertion",
                t_data.name,
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
        # Setup tests use their own method/path (e.g. POST /login),
        # not the target endpoint's method/path
        if t_data.scenario_type == "setup":
            test_method = t_data.method or endpoint.method
            test_path = t_data.path or endpoint.path
        else:
            test_method = endpoint.method
            test_path = endpoint.path

        test_obj = Test(
            test_suite_id=suite_id,
            endpoint_id=endpoint.id,
            name=(t_data.name or "")[:255],
            description=(t_data.description or "")[:1024],
            scenario_type=t_data.scenario_type,
            method=test_method,
            path=test_path,
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
    register_endpoint_id: uuid.UUID | None = None,
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

        register_endpoint = None
        if register_endpoint_id:
            register_endpoint = await db.scalar(select(Endpoint).where(Endpoint.id == register_endpoint_id))

        logger.info(
            "━━━ Suite %s: starting generation for %d endpoints (scenarios: %s) ━━━",
            suite_id, len(endpoint_ids), ", ".join(scenarios),
        )
        if auth_endpoint:
            logger.info("Auth endpoint resolved: %s %s", auth_endpoint.method, auth_endpoint.path)
        if register_endpoint:
            logger.info("Register endpoint resolved: %s %s", register_endpoint.method, register_endpoint.path)

        total_tests = 0
        setup_generated = False
        
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
                
                # Only inject setup tests if this endpoint requires auth and we haven't generated them yet
                include_setup = False
                if not setup_generated and _ep_has_auth(endpoint):
                    include_setup = True
                    setup_generated = True

                count = await _generate_for_endpoint(
                    db, suite_id, endpoint, ep_scenarios, auth_endpoint, register_endpoint, include_setup
                )
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
            if isinstance(p, dict) and p.get("name", "").lower() == "authorization":
                requires_auth = True
                break

    auth_endpoint_id = None
    register_endpoint_id = None
    if requires_auth:
        auth_ep, reg_ep = resolve_auth_endpoints(all_endpoints)
        login_candidates = [
            ep for ep in all_endpoints
            if ep.method.lower() == "post"
            and any(k in ep.path.lower() for k in ["login", "auth", "token", "signin", "sessions"])
        ]

        if auth_ep:
            auth_endpoint_id = auth_ep.id
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Could not auto-detect a unique authentication endpoint (found {len(login_candidates)} candidates). "
                "Generation of authenticated test suites requires an auth endpoint config. "
                "(Manual UI configuration pending in Week 4)."
            )

        if reg_ep:
            register_endpoint_id = reg_ep.id

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
        generate_test_suite_task, suite.id, payload.endpoint_ids, payload.scenarios,
        auth_endpoint_id, register_endpoint_id,
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