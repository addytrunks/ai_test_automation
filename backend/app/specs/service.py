from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Endpoint, Project, Spec
from app.specs.parser import parse_openapi_spec
from app.specs.schemas import ProjectCreate, ProjectUpdate


async def create_project(
    db: AsyncSession, user_id: uuid.UUID, payload: ProjectCreate
) -> Project:
    project = Project(
        user_id=user_id,
        name=payload.name,
        description=payload.description,
        target_base_url=payload.target_base_url,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def get_projects(db: AsyncSession, user_id: uuid.UUID) -> list[Project]:
    result = await db.execute(
        select(Project).where(Project.user_id == user_id).order_by(Project.created_at.desc())
    )
    return list(result.scalars().all())


async def get_project(
    db: AsyncSession, user_id: uuid.UUID, project_id: uuid.UUID
) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


async def update_project(
    db: AsyncSession, user_id: uuid.UUID, project_id: uuid.UUID, payload: ProjectUpdate
) -> Project:
    project = await get_project(db, user_id, project_id)
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return project


async def delete_project(
    db: AsyncSession, user_id: uuid.UUID, project_id: uuid.UUID
) -> None:
    project = await get_project(db, user_id, project_id)
    await db.delete(project)
    await db.commit()


async def ingest_spec(
    db: AsyncSession, user_id: uuid.UUID, project_id: uuid.UUID, file_content: bytes
) -> tuple[Spec, list[Endpoint]]:
    # Verify project exists and belongs to user
    await get_project(db, user_id, project_id)

    try:
        version, raw_dict, endpoints_data = parse_openapi_spec(file_content)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    spec = Spec(project_id=project_id, version=version, raw_content=raw_dict)
    db.add(spec)
    await db.flush()  # Get spec.id

    endpoints = []
    for ep_data in endpoints_data:
        ep = Endpoint(
            spec_id=spec.id,
            method=ep_data["method"],
            path=ep_data["path"],
            summary=ep_data["summary"],
            parameters=ep_data["parameters"],
            request_body=ep_data["request_body"],
            responses=ep_data["responses"],
        )
        db.add(ep)
        endpoints.append(ep)

    await db.commit()
    await db.refresh(spec)
    return spec, endpoints


async def get_specs(db: AsyncSession, project_id: uuid.UUID) -> list[Spec]:
    result = await db.execute(
        select(Spec).where(Spec.project_id == project_id).order_by(Spec.created_at.desc())
    )
    return list(result.scalars().all())


async def get_endpoints(db: AsyncSession, spec_id: uuid.UUID) -> list[Endpoint]:
    result = await db.execute(
        select(Endpoint).where(Endpoint.spec_id == spec_id).order_by(Endpoint.path, Endpoint.method)
    )
    return list(result.scalars().all())
