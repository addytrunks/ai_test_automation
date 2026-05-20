from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, UploadFile, status
from sqlalchemy import select

from app.deps import CurrentUser, DbSession
from app.models import Project, Spec
from app.specs import service
from app.specs.schemas import EndpointRead, ProjectCreate, ProjectRead, ProjectUpdate, SpecRead

router = APIRouter()


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(payload: ProjectCreate, user: CurrentUser, db: DbSession) -> ProjectRead:
    return await service.create_project(db, user.id, payload)  # type: ignore[return-value]


@router.get("/projects", response_model=list[ProjectRead])
async def list_projects(user: CurrentUser, db: DbSession) -> list[ProjectRead]:
    return await service.get_projects(db, user.id)  # type: ignore[return-value]


@router.get("/projects/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> ProjectRead:
    return await service.get_project(db, user.id, project_id)  # type: ignore[return-value]


@router.patch("/projects/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: uuid.UUID, payload: ProjectUpdate, user: CurrentUser, db: DbSession
) -> ProjectRead:
    return await service.update_project(db, user.id, project_id, payload)  # type: ignore[return-value]


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> None:
    await service.delete_project(db, user.id, project_id)


@router.post(
    "/projects/{project_id}/specs",
    response_model=SpecRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_spec(
    project_id: uuid.UUID, file: UploadFile, user: CurrentUser, db: DbSession
) -> SpecRead:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    spec, _ = await service.ingest_spec(db, user.id, project_id, content)
    return spec  # type: ignore[return-value]


@router.get("/projects/{project_id}/specs", response_model=list[SpecRead])
async def list_specs(
    project_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[SpecRead]:
    # Verify project belongs to user
    await service.get_project(db, user.id, project_id)
    return await service.get_specs(db, project_id)  # type: ignore[return-value]


@router.get("/specs/{spec_id}/endpoints", response_model=list[EndpointRead])
async def list_endpoints(
    spec_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[EndpointRead]:
    # Verify spec -> project -> user ownership chain
    stmt = select(Spec).join(Project).where(Spec.id == spec_id, Project.user_id == user.id)
    result = await db.execute(stmt)
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Spec not found")

    return await service.get_endpoints(db, spec_id)  # type: ignore[return-value]
