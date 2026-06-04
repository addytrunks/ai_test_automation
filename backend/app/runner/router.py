"""Runner API router.

Endpoints for triggering test runs, viewing results, and retrieving
AI failure analyses. All endpoints verify ownership through the
Run → TestSuite → Project → user_id chain.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agentic.checkpointer import get_checkpointer
from app.agentic.graph import build_graph
from app.agentic.state import AgenticLoopState
from app.analyzer.schemas import AIAnalysisRead, RunCreate, RunRead, TestResultRead
from app.deps import CurrentUser, DbSession
from app.models import AIAnalysis, Project, Run, Test, TestResult, TestSuite

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Ownership helpers
# ---------------------------------------------------------------------------


async def _verify_suite_ownership(
    db: AsyncSession, suite_id: uuid.UUID, user_id: uuid.UUID
) -> TestSuite:
    """Verify TestSuite → Project → user_id chain. Raises 404 if broken."""
    result = await db.execute(
        select(TestSuite)
        .join(Project)
        .where(TestSuite.id == suite_id, Project.user_id == user_id)
    )
    suite = result.scalar_one_or_none()
    if not suite:
        raise HTTPException(status_code=404, detail="Test suite not found")
    return suite


async def _verify_run_ownership(
    db: AsyncSession, run_id: uuid.UUID, user_id: uuid.UUID
) -> Run:
    """Verify Run → TestSuite → Project → user_id chain. Raises 404 if broken."""
    result = await db.execute(
        select(Run)
        .join(TestSuite)
        .join(Project)
        .where(Run.id == run_id, Project.user_id == user_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


async def _verify_test_result_ownership(
    db: AsyncSession, result_id: uuid.UUID, user_id: uuid.UUID
) -> TestResult:
    """Verify TestResult → Run → TestSuite → Project → user_id chain."""
    result = await db.execute(
        select(TestResult)
        .join(Run)
        .join(TestSuite)
        .join(Project)
        .where(TestResult.id == result_id, Project.user_id == user_id)
    )
    tr = result.scalar_one_or_none()
    if not tr:
        raise HTTPException(status_code=404, detail="Test result not found")
    return tr


# ---------------------------------------------------------------------------
# Agentic loop background task
# ---------------------------------------------------------------------------


async def run_agentic_loop(
    suite_id: uuid.UUID,
    target_base_url: str,
) -> None:
    """Background task: compile the LangGraph and invoke the agentic loop.

    Creates its own checkpointer and DB sessions (since BackgroundTasks
    run outside the request lifecycle).
    """
    try:
        async with get_checkpointer() as checkpointer:
            graph = build_graph(checkpointer=checkpointer)

            initial_state: AgenticLoopState = {
                "test_suite_id": str(suite_id),
                "target_base_url": target_base_url,
                "current_depth": 0,
                "max_depth": 3,
                "max_tests_per_cycle": 10,
                "last_run_id": None,
                "last_gaps": [],
                "new_test_ids": [],
                "total_tokens_used": 0,
                "final_status": None,
            }

            # thread_id is REQUIRED for the checkpointer to key state correctly.
            config = {"configurable": {"thread_id": str(suite_id)}}

            result = await graph.ainvoke(initial_state, config=config)
            logger.info(
                "Agentic loop completed for suite %s: status=%s, depth=%d, tokens=%d",
                suite_id,
                result.get("final_status"),
                result.get("current_depth", 0),
                result.get("total_tokens_used", 0),
            )
    except Exception:
        logger.exception("Agentic loop failed for suite %s", suite_id)


# ---------------------------------------------------------------------------
# Run endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/test-suites/{suite_id}/runs",
    response_model=RunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_run(
    suite_id: uuid.UUID,
    payload: RunCreate,
    background_tasks: BackgroundTasks,
    user: CurrentUser,
    db: DbSession,
) -> dict[str, str]:
    """Trigger an agentic test run for a suite against a target URL.

    Returns 202 Accepted immediately. The frontend should poll
    GET /test-suites/{suite_id}/runs to see loop iterations appear.
    """
    await _verify_suite_ownership(db, suite_id, user.id)

    # Verify suite has tests
    test_count = await db.execute(
        select(Test.id).where(Test.test_suite_id == suite_id).limit(1)
    )
    if not test_count.scalar_one_or_none():
        raise HTTPException(
            status_code=400, detail="Test suite has no tests to run"
        )

    # Enqueue the agentic loop — Run records are created by execute_run_node
    background_tasks.add_task(
        run_agentic_loop, suite_id, payload.target_base_url
    )

    return {"suite_id": str(suite_id), "status": "accepted"}


@router.get("/test-suites/{suite_id}/runs", response_model=list[RunRead])
async def list_runs(
    suite_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> list[RunRead]:
    """List all runs for a test suite."""
    await _verify_suite_ownership(db, suite_id, user.id)

    result = await db.execute(
        select(Run)
        .where(Run.test_suite_id == suite_id)
        .order_by(Run.started_at.desc().nulls_last())
    )
    return list(result.scalars().all())  # type: ignore[arg-type]


@router.get("/runs/{run_id}", response_model=RunRead)
async def get_run(
    run_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> RunRead:
    """Get a single run (used for polling status during execution)."""
    run = await _verify_run_ownership(db, run_id, user.id)
    return run  # type: ignore[return-value]


@router.get("/runs/{run_id}/results", response_model=list[TestResultRead])
async def list_run_results(
    run_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> list[TestResultRead]:
    """List all test results for a run."""
    await _verify_run_ownership(db, run_id, user.id)

    result = await db.execute(
        select(TestResult)
        .where(TestResult.run_id == run_id)
        .order_by(TestResult.created_at)
    )
    return list(result.scalars().all())  # type: ignore[arg-type]


@router.get("/test-results/{result_id}/analysis", response_model=AIAnalysisRead)
async def get_analysis(
    result_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> AIAnalysisRead:
    """Get the AI failure analysis for a test result.

    Returns 404 if the analysis hasn't been generated yet.
    The frontend uses this to show a loading spinner while the run is in 'analyzing' status.
    """
    await _verify_test_result_ownership(db, result_id, user.id)

    result = await db.execute(
        select(AIAnalysis).where(AIAnalysis.test_result_id == result_id)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not available yet")
    return analysis  # type: ignore[return-value]