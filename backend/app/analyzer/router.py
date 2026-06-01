"""Analyzer API router.

Provides a placeholder coverage analysis endpoint for Week 5.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.deps import CurrentUser, DbSession

router = APIRouter()


@router.post("/test-suites/{suite_id}/coverage-analyze")
async def coverage_analyze(
    suite_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> dict[str, list[str]]:
    """Placeholder for on-demand coverage analysis (Week 5).

    Will eventually identify untested scenario types and generate
    additional tests to fill coverage gaps.
    """
    return {"gaps": []}
