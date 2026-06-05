"""Pydantic schemas for the analyzer module.

Defines the structured output format the LLM must follow when
analyzing test failures, and the API response schemas.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# LLM output schema — enforced via generate_structured()
# ---------------------------------------------------------------------------


class FailureExplanation(BaseModel):
    """Structured analysis of a single test failure.

    This is used as the response_format for litellm, ensuring the LLM
    always returns these three fields in valid JSON.
    """

    explanation: str = Field(
        description="Plain-English explanation of what happened and why the test failed"
    )
    likely_cause: str = Field(
        description="Root cause category (e.g. BOLA vulnerability, missing auth check, validation bypass)"
    )
    suggested_fix: str = Field(
        description="Concrete remediation steps the API developer should take"
    )


# ---------------------------------------------------------------------------
# API response schemas
# ---------------------------------------------------------------------------


class RunCreate(BaseModel):
    """Request body for triggering a test run."""

    target_base_url: str = Field(
        default="http://localhost:5001",
        description="Base URL of the target API to test against",
    )


class RunAccepted(BaseModel):
    """Response schema for 202 Accepted when triggering an agentic run.

    The frontend should poll GET /test-suites/{suite_id}/runs
    to see loop iterations appear.
    """

    suite_id: uuid.UUID
    status: str = "accepted"


class RunRead(BaseModel):
    """Response schema for a run."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    test_suite_id: uuid.UUID
    target_base_url: str
    status: str
    summary: dict[str, Any] | None
    parent_run_id: uuid.UUID | None
    loop_iteration: int
    started_at: Any | None
    completed_at: Any | None


class TestResultRead(BaseModel):
    """Response schema for a single test result."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    test_id: uuid.UUID
    status: str
    response_status: int | None
    response_headers: dict[str, Any] | None
    response_body: Any | None
    duration_ms: int | None
    assertion_results: list[dict[str, Any]] | None
    error_message: str | None
    created_at: Any


class AIAnalysisRead(BaseModel):
    """Response schema for an AI failure analysis."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    test_result_id: uuid.UUID
    explanation: str
    likely_cause: str
    suggested_fix: str
    created_at: Any


class CoverageGapRead(BaseModel):
    """Response schema for a coverage gap."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    test_suite_id: uuid.UUID
    endpoint_id: uuid.UUID
    run_id: uuid.UUID
    scenario_description: str
    severity: str
    spawned_test_id: uuid.UUID | None
    created_at: Any
