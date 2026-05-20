from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    target_base_url: str | None = Field(default=None, max_length=1024)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    target_base_url: str | None = Field(default=None, max_length=1024)


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str | None
    target_base_url: str | None
    created_at: datetime


class SpecRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    version: str
    parsed_at: datetime
    created_at: datetime
    # We explicitly exclude raw_content from read to avoid massive payloads


class EndpointRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    spec_id: uuid.UUID
    method: str
    path: str
    summary: str | None
    parameters: list[dict[str, Any]] | None
    request_body: dict[str, Any] | None
    responses: dict[str, Any] | None
