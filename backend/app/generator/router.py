"""
Generator API router.

Exposes endpoints for creating test suites (triggering AI generation),
listing suites, polling suite status, and retrieving generated tests.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import select

from app.deps import CurrentUser, DbSession
from app.generator import service
from app.generator.schemas import TestRead, TestSuiteCreate, TestSuiteRead
from app.models import Project

router = APIRouter()


@router.post(
    "/projects/{project_id}/test-suites",
    response_model=TestSuiteRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_suite(
    project_id: uuid.UUID,
    payload: TestSuiteCreate,
    background_tasks: BackgroundTasks,
    user: CurrentUser,
    db: DbSession,
) -> TestSuiteRead:
    """Create a new test suite and trigger background AI generation."""
    # Verify project belongs to user
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    return await service.create_test_suite(db, project_id, payload, background_tasks)  # type: ignore[return-value]


@router.get("/projects/{project_id}/test-suites", response_model=list[TestSuiteRead])
async def list_suites(
    project_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> list[TestSuiteRead]:
    """List all test suites for a project."""
    # Verify project belongs to user
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    return await service.get_test_suites(db, project_id)  # type: ignore[return-value]


@router.get("/test-suites/{suite_id}", response_model=TestSuiteRead)
async def get_suite(
    suite_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> TestSuiteRead:
    """Get a single test suite (used for polling status during generation)."""
    suite = await service.get_test_suite(db, suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="Test suite not found")

    # Verify ownership via project
    result = await db.execute(
        select(Project).where(Project.id == suite.project_id, Project.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Test suite not found")

    return suite  # type: ignore[return-value]


@router.get("/test-suites/{suite_id}/tests", response_model=list[TestRead])
async def list_tests(
    suite_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> list[TestRead]:
    """List all generated tests in a test suite."""
    suite = await service.get_test_suite(db, suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="Test suite not found")

    # Verify ownership via project
    result = await db.execute(
        select(Project).where(Project.id == suite.project_id, Project.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Test suite not found")

    return await service.get_tests(db, suite_id)  # type: ignore[return-value]


@router.delete("/test-suites/{suite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_suite(
    suite_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> None:
    """Delete a test suite and all its generated tests."""
    suite = await service.get_test_suite(db, suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="Test suite not found")

    # Verify ownership via project
    result = await db.execute(
        select(Project).where(Project.id == suite.project_id, Project.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Test suite not found")

    await service.delete_test_suite(db, suite_id)
