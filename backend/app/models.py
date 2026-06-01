from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    target_base_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Spec(Base):
    __tablename__ = "specs"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_content: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=False
    )
    parsed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Endpoint(Base):
    __tablename__ = "endpoints"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        primary_key=True,
        default=uuid.uuid4,
    )
    spec_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("specs.id", ondelete="CASCADE"), index=True
    )
    method: Mapped[str] = mapped_column(String(10), nullable=False)  # GET, POST, etc
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    summary: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    parameters: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True
    )
    request_body: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True
    )
    responses: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True
    )
    security: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True,
        comment="Per-operation security requirements from OpenAPI spec",
    )


class TestSuite(Base):
    __tablename__ = "test_suites"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    spec_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("specs.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    current_generation_depth: Mapped[int] = mapped_column(Integer, default=0)
    auto_loop_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_loop_max_depth: Mapped[int] = mapped_column(Integer, default=3)
    auto_loop_max_tests_per_cycle: Mapped[int] = mapped_column(Integer, default=5)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Test(Base):
    __tablename__ = "tests"
    __table_args__ = (
        UniqueConstraint("test_suite_id", "generation_hash", name="uq_test_suite_gen_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        primary_key=True,
        default=uuid.uuid4,
    )
    test_suite_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_suites.id", ondelete="CASCADE"), index=True
    )
    endpoint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("endpoints.id", ondelete="CASCADE"), index=True
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    scenario_type: Mapped[str] = mapped_column(String(50), nullable=False)

    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    path_params: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True
    )
    query_params: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True
    )
    headers: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True
    )
    body: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True
    )

    expected_status: Mapped[int] = mapped_column(Integer, nullable=False)
    assertions: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True
    )
    extract: Mapped[dict[str, str] | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True,
        comment="Maps template var names to JSONPath expressions for setup tests",
    )
    static_context: Mapped[dict[str, str] | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True,
        comment="Static variable mappings for runtime context (e.g. USER_B_ID: 'user2')",
    )

    auto_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    parent_coverage_gap_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"), nullable=True
    )
    generation_depth: Mapped[int] = mapped_column(Integer, default=0)
    generation_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        primary_key=True,
        default=uuid.uuid4,
    )
    test_suite_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_suites.id", ondelete="CASCADE"), index=True
    )
    target_base_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending"
    )  # pending / running / analyzing / completed
    summary: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True
    )  # {total, passed, failed, errors}
    parent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        ForeignKey("runs.id"),
        nullable=True,
    )
    loop_iteration: Mapped[int] = mapped_column(Integer, default=0)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class TestResult(Base):
    __tablename__ = "test_results"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        primary_key=True,
        default=uuid.uuid4,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), index=True
    )
    test_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tests.id", ondelete="CASCADE"), index=True
    )

    status: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # passed / failed / error / skipped
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_headers: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True
    )
    response_body: Mapped[dict[str, Any] | str | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    assertion_results: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AIAnalysis(Base):
    __tablename__ = "ai_analyses"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        primary_key=True,
        default=uuid.uuid4,
    )
    test_result_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_results.id", ondelete="CASCADE"), unique=True, index=True
    )
    explanation: Mapped[str] = mapped_column(String, nullable=False)
    likely_cause: Mapped[str] = mapped_column(String, nullable=False)
    suggested_fix: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
