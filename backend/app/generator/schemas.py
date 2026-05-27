"""
Pydantic schemas for the generator module.

Defines the strict output format the LLM must follow when generating tests,
as well as the API request/response schemas for test suites and tests.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# LLM output schemas — these define *what the AI returns*
# ---------------------------------------------------------------------------


class AssertionSchema(BaseModel):
    """A single assertion rule to evaluate against an HTTP response."""

    type: Literal[
        "status_eq",
        "status_in",
        "json_path",
        "body_contains",
        "body_not_contains",
        "header_eq",
        "response_time_lt",
    ]
    target: str | None = None
    op: str | None = None
    expected: Any | None = None


class GeneratedTestSchema(BaseModel):
    """Schema for a single test case as returned by the LLM."""

    name: str = Field(description="Short descriptive name for the test")
    description: str = Field(description="Detailed explanation of what the test verifies")
    scenario_type: Literal[
        "positive", "negative", "auth_bypass", "bola", "boundary", "injection",
        "mass_assignment", "setup",
    ]

    path_params: dict[str, Any] | None = Field(
        default=None, description="Path parameters to inject"
    )
    query_params: dict[str, Any] | None = Field(
        default=None, description="Query string parameters"
    )
    headers: dict[str, Any] | None = Field(default=None, description="HTTP headers")
    body: dict[str, Any] | None = Field(default=None, description="JSON request body")
    extract: dict[str, str] | None = Field(
        default=None,
        description="Maps template variable names to JSONPath expressions for setup tests",
    )

    expected_status: int = Field(description="Expected HTTP status code")
    assertions: list[AssertionSchema] = Field(
        description="List of assertions to run against response"
    )


class TestListResult(BaseModel):
    """Wrapper for the list of tests returned by the LLM in a single call."""

    tests: list[GeneratedTestSchema]


# ---------------------------------------------------------------------------
# API request/response schemas
# ---------------------------------------------------------------------------


class TestSuiteCreate(BaseModel):
    """Request body for creating a new test suite and triggering generation."""

    name: str
    spec_id: uuid.UUID
    endpoint_ids: list[uuid.UUID]
    scenarios: list[str] = ["positive", "negative"]


class TestSuiteRead(BaseModel):
    """Response schema for a test suite."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    spec_id: uuid.UUID
    name: str
    status: str
    created_at: Any
    updated_at: Any


class TestRead(BaseModel):
    """Response schema for a single test."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    test_suite_id: uuid.UUID
    endpoint_id: uuid.UUID
    name: str
    description: str | None
    scenario_type: str
    method: str
    path: str
    path_params: dict[str, Any] | None
    query_params: dict[str, Any] | None
    headers: dict[str, Any] | None
    body: dict[str, Any] | None
    expected_status: int
    assertions: list[dict[str, Any]] | None
    extract: dict[str, str] | None = None
