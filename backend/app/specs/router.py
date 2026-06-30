from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, UploadFile, status
from sqlalchemy import select

from app.deps import CurrentUser, DbSession
from app.generator.service import resolve_auth_endpoints
from app.models import Endpoint, Project, Spec
from app.specs import service
from app.specs.schemas import (
    AuthEndpointHint,
    EndpointRead,
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
    SpecRead,
)

router = APIRouter()

# Auth keyword lists — kept in sync with generator.service.resolve_auth_endpoints
# NOTE: bare 'auth' intentionally excluded from login — it matches all /auth/* paths
_LOGIN_KEYWORDS = ["login", "authenticate", "token", "signin", "sessions"]
_REGISTER_KEYWORDS = ["register", "signup", "sign-up", "create-user"]


@router.get("/specs/{spec_id}/auth-endpoint-hint", response_model=AuthEndpointHint)
async def get_auth_endpoint_hint(
    spec_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> AuthEndpointHint:
    """Run the auth-detection heuristic and return candidates + recommendation.

    This is called at spec-load time so the UI can pre-populate the auth
    endpoint selector rather than failing at generation time.
    """
    # Verify ownership
    stmt = select(Spec).join(Project).where(Spec.id == spec_id, Project.user_id == user.id)
    result = await db.execute(stmt)
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Spec not found")

    all_endpoints = list(
        (await db.execute(select(Endpoint).where(Endpoint.spec_id == spec_id))).scalars().all()
    )

    # Collect candidates — register-first to exclude from login matches
    register_candidates = [
        ep for ep in all_endpoints
        if ep.method.lower() == "post"
        and any(k in ep.path.lower() for k in _REGISTER_KEYWORDS)
    ]
    register_ids = {ep.id for ep in register_candidates}
    login_candidates = [
        ep for ep in all_endpoints
        if ep.method.lower() == "post"
        and ep.id not in register_ids
        and any(k in ep.path.lower() for k in _LOGIN_KEYWORDS)
    ]

    # Auto-select if exactly one match
    login_id = login_candidates[0].id if len(login_candidates) == 1 else None
    register_id = register_candidates[0].id if len(register_candidates) == 1 else None

    return AuthEndpointHint(
        login_endpoint_id=login_id,
        login_candidates=login_candidates,  # type: ignore[arg-type]
        register_endpoint_id=register_id,
        register_candidates=register_candidates,  # type: ignore[arg-type]
    )


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
