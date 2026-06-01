"""Runner service — background task orchestration.

Entry point for test execution background tasks:
1. Calls execute_run() (sets run status to 'analyzing')
2. Fetches all failed TestResult rows
3. Calls analyze_failure() on each, committing individually
4. Sets run.status = 'completed'
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select

from app.analyzer.failure_analysis import analyze_failure
from app.models import Run, Test, TestResult
from app.runner.executor import execute_run

logger = logging.getLogger(__name__)


async def run_and_analyze_task(
    suite_id: uuid.UUID,
    run_id: uuid.UUID,
    target_base_url: str,
) -> None:
    """Background task: execute tests, then analyze failures.

    Creates its own DB session (since BackgroundTasks run outside the
    request lifecycle). Follows the same pattern as generator service.
    """
    from app.db import get_sessionmaker

    session_factory = get_sessionmaker()

    async with session_factory() as db:
        # Fetch all tests for this suite
        result = await db.execute(
            select(Test)
            .where(Test.test_suite_id == suite_id)
            .order_by(Test.path, Test.method)
        )
        tests = list(result.scalars().all())

        if not tests:
            logger.warning("No tests found for suite %s, marking run as completed", suite_id)
            run = await db.get(Run, run_id)
            if run:
                run.status = "completed"
                run.summary = {"total": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0}
                await db.commit()
            return

        logger.info(
            "━━━ Run %s: executing %d tests against %s ━━━",
            run_id, len(tests), target_base_url,
        )

        # Phase 1: Execute all tests (sets status to 'analyzing')
        await execute_run(db, run_id, tests, target_base_url)

        # Phase 2: Analyze failures progressively
        run = await db.get(Run, run_id)
        if not run or run.status == "error":
            logger.warning("Run %s ended in error status, skipping analysis", run_id)
            return

        failed_results = await db.execute(
            select(TestResult).where(
                TestResult.run_id == run_id,
                TestResult.status == "failed",
            )
        )
        failed_list = list(failed_results.scalars().all())

        if failed_list:
            logger.info(
                "━━━ Run %s: analyzing %d failed tests ━━━",
                run_id, len(failed_list),
            )
            for idx, tr in enumerate(failed_list, 1):
                logger.info(
                    "Analyzing failure %d/%d (result %s)...",
                    idx, len(failed_list), tr.id,
                )
                await analyze_failure(db, tr.id)
        else:
            logger.info("Run %s: all tests passed, no failures to analyze", run_id)

        # Phase 3: Mark run as completed
        # Re-fetch run in case the session state changed
        run = await db.get(Run, run_id)
        if run:
            run.status = "completed"
            await db.commit()
            logger.info("━━━ Run %s: completed ━━━", run_id)
