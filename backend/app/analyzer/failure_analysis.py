"""Failure analysis service.

Fetches a failed TestResult + its parent Test, builds a 3-layer prompt,
calls the LLM via generate_structured(), and persists the AIAnalysis row.
Each analysis is committed individually for progressive frontend display.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.analyzer.prompts import FAILURE_ANALYSIS_SYSTEM_PROMPT, build_failure_prompt
from app.analyzer.schemas import FailureExplanation
from app.llm.client import generate_structured
from app.models import AIAnalysis, Test, TestResult

logger = logging.getLogger(__name__)


async def analyze_failure(db: AsyncSession, test_result_id: uuid.UUID) -> None:
    """Analyze a single failed test result using the LLM.

    Skips silently if the result doesn't exist or isn't in 'failed' status.
    Commits the AIAnalysis row immediately so the frontend can poll for it.
    """
    tr = await db.get(TestResult, test_result_id)
    if not tr or tr.status != "failed":
        return

    test = await db.get(Test, tr.test_id)
    if not test:
        logger.warning("Test %s not found for result %s, skipping analysis", tr.test_id, test_result_id)
        return

    prompt = build_failure_prompt(
        test_name=test.name,
        test_description=test.description,
        scenario_type=test.scenario_type,
        method=test.method,
        path=test.path,
        expected_status=test.expected_status,
        assertions=test.assertions,
        response_status=tr.response_status,
        response_body=tr.response_body,
        assertion_results=tr.assertion_results,
    )

    try:
        result = await generate_structured(
            prompt=prompt,
            response_model=FailureExplanation,
            system_prompt=FAILURE_ANALYSIS_SYSTEM_PROMPT,
            temperature=0.1,  # Low: failure analysis should be deterministic, not creative
        )

        analysis = AIAnalysis(
            test_result_id=tr.id,
            explanation=result.explanation,
            likely_cause=result.likely_cause,
            suggested_fix=result.suggested_fix,
        )
        db.add(analysis)
        await db.commit()
        logger.info("Analysis saved for test result %s", test_result_id)
    except Exception as e:
        logger.warning("Failed to analyze test result %s: %s", test_result_id, e)
