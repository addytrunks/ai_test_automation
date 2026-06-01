"""Two-pass HTTP test executor.

Pass 1: Execute setup tests sequentially, extract variables via jsonpath,
        populate runtime_context. Dedup setup tests whose extract keys are
        already resolved.
Pass 2: Execute remaining tests with all template variables resolved via
        recursive interpolate_payload().

Both passes persist TestResult rows through the same path.
Run status transitions: pending → running → analyzing (service layer sets completed).
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from jsonpath_ng import parse as jp_parse  # type: ignore[import-untyped]
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Run, Test, TestResult
from app.runner.assertions import evaluate_assertions

logger = logging.getLogger(__name__)


# ── Template variable resolution ─────────────────────────────────────────────


def interpolate_payload(obj: Any, context: dict[str, str]) -> Any:
    """Recursively resolve ``{{VAR}}`` placeholders in dicts, lists, and strings.

    Non-string scalars (int, bool, float, None) pass through untouched.
    """
    if obj is None:
        return None
    if isinstance(obj, str):
        return re.sub(
            r"\{\{(\w+)\}\}",
            lambda m: context.get(m.group(1), m.group(0)),
            obj,
        )
    if isinstance(obj, dict):
        return {k: interpolate_payload(v, context) for k, v in obj.items()}
    if isinstance(obj, list):
        return [interpolate_payload(item, context) for item in obj]
    # int, bool, float — pass through
    return obj


# ── Single-test execution ────────────────────────────────────────────────────


async def _execute_single_test(
    client: httpx.AsyncClient,
    db: AsyncSession,
    run: Run,
    test: Test,
    base_url: str,
    runtime_context: dict[str, str],
) -> TestResult:
    """Execute one test, persist a TestResult row, and return it."""

    # Resolve template variables in all payloads
    path = interpolate_payload(test.path, runtime_context)
    headers = interpolate_payload(test.headers, runtime_context)
    body = interpolate_payload(test.body, runtime_context)
    query_params = interpolate_payload(test.query_params, runtime_context)

    # Resolve path params (e.g. {username} → "admin") — after template vars
    path_params = interpolate_payload(test.path_params, runtime_context)
    if path_params:
        for k, v in path_params.items():
            path = path.replace(f"{{{k}}}", str(v))

    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"

    start_time = time.time()
    error_message: str | None = None
    response_status: int | None = None
    response_headers_dict: dict[str, Any] | None = None
    response_body: dict[str, Any] | str | None = None
    duration_ms: int | None = None
    all_passed = False
    assertion_results: list[dict[str, Any]] = []
    status = "error"

    try:
        response = await client.request(
            method=test.method.upper(),
            url=url,
            params=query_params,
            headers=headers,
            json=body if body else None,
        )
        duration_ms = int((time.time() - start_time) * 1000)
        response_status = response.status_code
        response_headers_dict = dict(response.headers)

        try:
            response_body = response.json()
        except Exception:
            response_body = {"raw": response.text}

        all_passed, assertion_results = evaluate_assertions(
            test.assertions or [],
            response_status,
            response_headers_dict,
            response_body,
            duration_ms,
        )
        status = "passed" if all_passed else "failed"
    except Exception as e:
        error_message = str(e)
        duration_ms = int((time.time() - start_time) * 1000)

    tr = TestResult(
        run_id=run.id,
        test_id=test.id,
        status=status,
        response_status=response_status,
        response_headers=response_headers_dict,
        response_body=response_body,
        duration_ms=duration_ms,
        assertion_results=assertion_results,
        error_message=error_message,
    )
    db.add(tr)
    return tr


# ── Two-pass orchestrator ─────────────────────────────────────────────────────


async def execute_run(
    db: AsyncSession,
    run_id: uuid.UUID,
    tests: list[Test],
    base_url: str,
) -> None:
    """Execute all tests in a suite run using the two-pass strategy.

    1. Setup tests first (sequential, populate runtime_context, dedup).
    2. Remaining tests with resolved template variables.

    Sets run.status to ``"analyzing"`` on completion — the service layer
    is responsible for running failure analysis and setting ``"completed"``.
    """
    run = await db.get(Run, run_id)
    if run is None:
        logger.error("Run %s not found, aborting execution", run_id)
        return

    run.status = "running"
    run.started_at = datetime.now(timezone.utc)
    await db.commit()

    summary = {"total": len(tests), "passed": 0, "failed": 0, "errors": 0}
    runtime_context: dict[str, str] = {}

    # Split tests into setup and execution phases
    setup_tests = [t for t in tests if t.scenario_type == "setup"]
    exec_tests = [t for t in tests if t.scenario_type != "setup"]

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # ── Pass 1: Setup tests (sequential, populate runtime_context) ──
            for test in setup_tests:
                # Dedup: skip if all extract keys are already populated
                if test.extract and all(
                    k in runtime_context for k in test.extract
                ):
                    logger.info(
                        "Skipping duplicate setup test '%s' — context already has %s",
                        test.name,
                        list(test.extract.keys()),
                    )
                    summary["total"] -= 1  # don't count skipped in total
                    continue

                tr = await _execute_single_test(
                    client, db, run, test, base_url, runtime_context
                )

                # Extract values from response for runtime context
                if (
                    tr.status == "passed"
                    and test.extract
                    and isinstance(tr.response_body, dict)
                ):
                    for var_name, jsonpath_expr in test.extract.items():
                        try:
                            matches = jp_parse(jsonpath_expr).find(
                                tr.response_body
                            )
                            if matches:
                                runtime_context[var_name] = str(
                                    matches[0].value
                                )
                                logger.info(
                                    "Setup extracted %s = %s...",
                                    var_name,
                                    str(matches[0].value)[:20],
                                )
                        except Exception as e:
                            logger.warning(
                                "Failed to extract %s: %s", var_name, e
                            )

                # Merge static_context
                if test.static_context:
                    runtime_context.update(test.static_context)

                if tr.status == "passed":
                    summary["passed"] += 1
                elif tr.status == "failed":
                    summary["failed"] += 1
                else:
                    summary["errors"] += 1

            # ── Pass 2: Execute remaining tests with resolved context ──
            for test in exec_tests:
                tr = await _execute_single_test(
                    client, db, run, test, base_url, runtime_context
                )

                if tr.status == "passed":
                    summary["passed"] += 1
                elif tr.status == "failed":
                    summary["failed"] += 1
                else:
                    summary["errors"] += 1

    except Exception as e:
        logger.exception("Unexpected error during run %s: %s", run_id, e)
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        run.summary = {**summary, "errors": summary["errors"] + 1}
        await db.commit()
        return

    # Transition to analyzing — service layer handles failure analysis
    run.status = "analyzing"
    run.completed_at = datetime.now(timezone.utc)
    run.summary = summary
    await db.commit()
