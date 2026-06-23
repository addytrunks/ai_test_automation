"""Agentic loop graph nodes.

Each node is an async function that receives the current AgenticLoopState,
performs work, and returns a partial state update dict. Nodes that access
the database create their own AsyncSession via get_sessionmaker() because
they run in a background task outside the request lifecycle.

Node flow: execute_run -> analyze -> [decide_continue] -> generate | finalize
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio.session import async_sessionmaker

from app.agentic.dedup import (
    compute_generation_hash,
    infer_scenario_type,
    scenario_is_sufficiently_covered,
)
from app.agentic.state import AgenticLoopState
from app.analyzer.coverage_analysis import analyze_coverage_gaps
from app.analyzer.failure_analysis import analyze_failure
from app.models import CoverageGap, Endpoint, Run, Test, TestResult
from app.runner.executor import execute_run

logger = logging.getLogger(__name__)


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Lazy import to avoid circular imports at module load time."""
    from app.db import get_sessionmaker
    return get_sessionmaker()


# ---------------------------------------------------------------------------
# Node 1: execute_run_node
# ---------------------------------------------------------------------------


async def execute_run_node(state: AgenticLoopState) -> dict[str, Any]:
    """Execute tests and create a Run record.

    On depth 0: runs ALL tests in the suite (initial baseline).
    On depth > 0: runs ONLY the tests in state["new_test_ids"] to avoid
    redundantly re-executing the entire suite.
    """
    session_factory = _get_session_factory()
    suite_id = uuid.UUID(state["test_suite_id"])
    depth = state["current_depth"]
    logger.info(f"==> [execute_run_node] Starting execution for suite {suite_id} at depth {depth}")

    async with session_factory() as db:
        # Determine which tests to execute
        if depth == 0:
            # First iteration: run the entire suite
            result = await db.execute(
                select(Test)
                .where(Test.test_suite_id == suite_id)
                .order_by(Test.path, Test.method)
            )
            tests = list(result.scalars().all())
        else:
            # Subsequent iterations: run ONLY newly generated tests + setup tests
            new_ids = [uuid.UUID(tid) for tid in state["new_test_ids"]]
            if not new_ids:
                logger.warning("No new_test_ids at depth %d, skipping execution", depth)
                return {"last_run_id": state["last_run_id"]}

            # We MUST include the suite's setup tests so runtime_context is populated
            result = await db.execute(
                select(Test)
                .where(
                    (Test.id.in_(new_ids)) | 
                    ((Test.test_suite_id == suite_id) & (Test.scenario_type == "setup"))
                )
                .order_by(Test.path, Test.method)
            )
            tests = list(result.scalars().all())

        if not tests:
            logger.warning("No tests found for suite %s at depth %d", suite_id, depth)
            return {"last_run_id": state["last_run_id"]}

        # Create a new Run record for this iteration
        run = Run(
            test_suite_id=suite_id,
            target_base_url=state["target_base_url"],
            status="pending",
            parent_run_id=uuid.UUID(state["last_run_id"]) if state["last_run_id"] else None,
            loop_iteration=depth,
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)

        logger.info(
            "━━━ Agentic Run %s (depth %d): executing %d tests ━━━",
            run.id, depth, len(tests),
        )

        # Execute via the existing two-pass executor
        await execute_run(db, run.id, tests, state["target_base_url"])

        return {
            "last_run_id": str(run.id),
            "current_depth": depth + 1,
            "new_test_ids": [],  # Reset for next iteration
        }


# ---------------------------------------------------------------------------
# Node 2: analyze_node
# ---------------------------------------------------------------------------


async def analyze_node(state: AgenticLoopState) -> dict[str, Any]:
    """Analyze failures and identify coverage gaps.

    Two-phase analysis:
    1. Failure analysis: generate AIAnalysis for each failed test result.
    2. Coverage gap analysis: use the LLM to find untested scenarios.

    Token usage from both phases is returned for the add-reducer
    on total_tokens_used.
    """
    # Guard: if execute_run_node returned early with no run, skip analysis
    if not state["last_run_id"]:
        logger.warning("analyze_node called with no last_run_id, skipping")
        return {"last_gaps": [], "total_tokens_used": 0}

    session_factory = _get_session_factory()
    suite_id = uuid.UUID(state["test_suite_id"])
    run_id = uuid.UUID(state["last_run_id"])

    tokens_this_step = 0

    async with session_factory() as db:
        # Update run status to 'analyzing'
        run = await db.get(Run, run_id)
        if run:
            run.status = "analyzing"
            await db.commit()

        # Phase 1: Failure analysis (per-result LLM calls)
        failed_results = await db.execute(
            select(TestResult).where(
                TestResult.run_id == run_id,
                TestResult.status == "failed",
            )
        )
        failed_list = list(failed_results.scalars().all())

        if failed_list:
            logger.info(
                "━━━ Analyzing %d failures for run %s ━━━",
                len(failed_list), run_id,
            )
            failed_ids = [tr.id for tr in failed_list]
            for tr_id in failed_ids:
                tokens = await analyze_failure(db, tr_id)
                tokens_this_step += tokens

        # Phase 2: Coverage gap analysis
        gaps, gap_tokens = await analyze_coverage_gaps(db, suite_id, run_id)
        tokens_this_step += gap_tokens

        # Serialize gaps for state (TypedDict requires JSON-serializable values)
        serialized_gaps = [
            {
                "id": str(g.id),
                "endpoint_id": str(g.endpoint_id),
                "scenario_description": g.scenario_description,
                "scenario_type": infer_scenario_type(g.scenario_description),
                "severity": g.severity,
            }
            for g in gaps
        ]

        # Mark run as completed
        run = await db.get(Run, run_id)
        if run:
            run.status = "completed"
            run.completed_at = datetime.now(UTC)
            await db.commit()

        logger.info(
            "━━━ Analysis complete: %d failures analyzed, %d gaps found (tokens: %d) ━━━",
            len(failed_list), len(gaps), tokens_this_step,
        )

    return {
        "last_gaps": serialized_gaps,
        "total_tokens_used": tokens_this_step,  # add-reducer accumulates
    }


# ---------------------------------------------------------------------------
# Node 3: generate_node
# ---------------------------------------------------------------------------


async def generate_node(state: AgenticLoopState) -> dict[str, Any]:
    """Generate new tests from coverage gaps.

    Reads high-severity gaps from state, asks the LLM to generate targeted
    tests, deduplicates via generation_hash, and persists to the database.
    Uses savepoints (begin_nested) for IntegrityError handling so that a
    duplicate hash on one test doesn't roll back previously flushed tests.
    """
    from app.generator.prompts import build_generation_prompt
    from app.generator.schemas import TestListResult
    from app.generator.service import (
        SYSTEM_PROMPT,
        _endpoint_to_prompt_dict,
        _ep_has_auth,
        resolve_auth_endpoints,
    )
    from app.llm.client import generate_structured_with_usage
    from app.models import TestSuite

    session_factory = _get_session_factory()
    suite_id = uuid.UUID(state["test_suite_id"])
    depth = state["current_depth"]
    max_tests = min(state["max_tests_per_cycle"], 10)

    # Filter to high-severity gaps only
    high_gaps = [g for g in state["last_gaps"] if g.get("severity") == "high"]
    if not high_gaps:
        logger.info("No high-severity gaps to generate tests for")
        return {"new_test_ids": [], "total_tokens_used": 0}

    # Limit to max_tests_per_cycle
    gaps_to_process = high_gaps[:max_tests]
    tokens_this_step = 0
    new_test_ids: list[str] = []

    async with session_factory() as db:
        suite = await db.get(TestSuite, suite_id)
        auth_endpoint = None
        register_endpoint = None
        if suite:
            all_eps = list(
                (
                    await db.execute(select(Endpoint).where(Endpoint.spec_id == suite.spec_id))
                ).scalars().all()
            )
            auth_endpoint, register_endpoint = resolve_auth_endpoints(all_eps)

        suite_tests = list(
            (
                await db.execute(select(Test).where(Test.test_suite_id == suite_id))
            ).scalars().all()
        )

        existing_hashes_result = await db.execute(
            select(Test.generation_hash).where(
                Test.test_suite_id == suite_id,
                Test.generation_hash.isnot(None),
            )
        )
        existing_hashes = set(existing_hashes_result.scalars().all())

        for gap in gaps_to_process:
            endpoint_id = uuid.UUID(gap["endpoint_id"])
            endpoint = await db.get(Endpoint, endpoint_id)
            if not endpoint:
                logger.warning("Endpoint %s not found, skipping gap", endpoint_id)
                continue

            if scenario_is_sufficiently_covered(
                suite_tests, endpoint_id, gap["scenario_description"]
            ):
                logger.info(
                    "Skipping gap — scenario already covered: %s",
                    gap["scenario_description"][:80],
                )
                continue

            ep_dict = _endpoint_to_prompt_dict(endpoint)

            scenario = gap.get("scenario_type") or infer_scenario_type(
                gap["scenario_description"]
            )
            needs_auth_context = scenario in (
                "bola", "mass_assignment", "injection", "positive", "negative", "boundary"
            ) and _ep_has_auth(endpoint)

            auth_dict = (
                _endpoint_to_prompt_dict(auth_endpoint) if auth_endpoint else None
            )
            reg_dict = (
                _endpoint_to_prompt_dict(register_endpoint) if register_endpoint else None
            )

            prompt = build_generation_prompt(
                ep_dict,
                [scenario],
                auth_endpoint_dict=auth_dict,
                register_endpoint_dict=reg_dict,
                include_setup=False,
                include_auth_context=needs_auth_context,
                gap_mode=True,
                gap_description=gap["scenario_description"],
            )
            # Track tests spawned specifically for THIS gap
            gap_test_ids: list[str] = []

            try:
                result, tokens_used = await generate_structured_with_usage(
                    prompt=prompt,
                    response_model=TestListResult,
                    system_prompt=SYSTEM_PROMPT,
                    temperature=0.4,
                )
                tokens_this_step += tokens_used

                for t_data in result.tests:
                    test_method = (
                        t_data.method or endpoint.method
                        if t_data.scenario_type == "setup"
                        else endpoint.method
                    )
                    test_path = (
                        t_data.path or endpoint.path
                        if t_data.scenario_type == "setup"
                        else endpoint.path
                    )
                    gen_hash = compute_generation_hash(
                        str(endpoint_id),
                        t_data.scenario_type,
                        test_method,
                        test_path,
                        path_params=t_data.path_params,
                        query_params=t_data.query_params,
                        body=t_data.body if isinstance(t_data.body, dict) else None,
                        expected_status=t_data.expected_status,
                    )

                    # Skip if already exists in memory set
                    if gen_hash in existing_hashes:
                        logger.info("Skipping duplicate test: %s", t_data.name)
                        continue

                    test = Test(
                        test_suite_id=suite_id,
                        endpoint_id=endpoint_id,
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
                        assertions=[
                            a.model_dump(exclude_none=True) for a in t_data.assertions
                        ],
                        auto_generated=True,
                        parent_coverage_gap_id=uuid.UUID(gap["id"]),
                        generation_depth=depth,
                        generation_hash=gen_hash,
                    )
                    db.add(test)

                    try:
                        # Savepoint so a duplicate hash only rolls back this insert,
                        # not all previously flushed tests in the session.
                        async with db.begin_nested():
                            await db.flush()
                        existing_hashes.add(gen_hash)
                        gap_test_ids.append(str(test.id))
                        new_test_ids.append(str(test.id))
                        suite_tests.append(test)
                        logger.info("Generated test: %s (hash: %s...)", t_data.name, gen_hash[:12])
                    except IntegrityError:
                        logger.info("Duplicate hash detected by DB constraint, skipping: %s", t_data.name)
                        continue

                # Link gap to the first test spawned specifically for it
                if gap_test_ids:
                    gap_obj = await db.get(CoverageGap, uuid.UUID(gap["id"]))
                    if gap_obj:
                        gap_obj.spawned_test_id = uuid.UUID(gap_test_ids[0])

            except Exception:
                logger.exception("Failed to generate tests for gap: %s", gap["scenario_description"])
                continue

        await db.commit()
        logger.info(
            "━━━ Generated %d new tests at depth %d (tokens: %d) ━━━",
            len(new_test_ids), depth, tokens_this_step,
        )

    return {
        "new_test_ids": new_test_ids,
        "total_tokens_used": tokens_this_step,  # add-reducer accumulates
    }


# ---------------------------------------------------------------------------
# Routing function (pure — no state mutation)
# ---------------------------------------------------------------------------


def decide_continue(state: AgenticLoopState) -> Literal["continue", "finalize"]:
    """Pure routing function. Returns a routing key only. Does NOT mutate state.

    Routes to "finalize" if:
    - max_depth reached (clamped to 5)
    - token budget exceeded (200,000)
    - no high-severity gaps remain
    """
    if state["current_depth"] >= min(state["max_depth"], 5):
        return "finalize"
    if state["total_tokens_used"] >= 200_000:
        return "finalize"
    high = [g for g in state["last_gaps"] if g.get("severity") == "high"]
    if not high:
        return "finalize"
    return "continue"


# ---------------------------------------------------------------------------
# Terminal node
# ---------------------------------------------------------------------------


def finalize_node(state: AgenticLoopState) -> dict[str, Any]:
    """Set the terminal status based on why the loop is ending."""
    if state["current_depth"] >= min(state["max_depth"], 5):
        reason = "max_depth_hit"
    elif state["total_tokens_used"] >= 200_000:
        reason = "token_budget_hit"
    else:
        high = [g for g in state["last_gaps"] if g.get("severity") == "high"]
        reason = "no_high_gaps" if not high else "completed"

    logger.info(
        "━━━ Agentic loop finalized: %s (depth=%d, tokens=%d) ━━━",
        reason, state["current_depth"], state["total_tokens_used"],
    )
    return {"final_status": reason}
