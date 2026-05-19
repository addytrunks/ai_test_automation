# Week 2 Implementation Plan — Spec Ingestion

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow users to create projects, upload OpenAPI 3.x specifications (JSON/YAML), parse those specs to extract endpoints, and browse the extracted endpoints in the UI.

**Architecture:** We will add the `projects`, `specs`, and `endpoints` tables. Parsing will use `prance` and `openapi-spec-validator` to fully resolve $refs and extract endpoint details. The frontend will get a Dashboard (listing projects), a Project detail page (for spec upload), and an Endpoint Explorer view.

**Tech Stack Additions:** `prance`, `openapi-spec-validator`, `PyYAML`. React components for file upload and tabular data display.

**Verification gate:** You can log in, create a project called "VAmPI Test", upload `vampi.json`, and see a list of extracted endpoints (like `GET /users`, `POST /users/login`) with their methods and paths correctly identified.

---

## File Structure for Week 2

**Backend (`backend/`):**
- Modify: `app/models.py` — add Project, Spec, Endpoint
- Add migration: `alembic/versions/..._add_spec_models.py`
- Create: `app/specs/__init__.py`
- Create: `app/specs/schemas.py` — Pydantic models for the new entities
- Create: `app/specs/parser.py` — Prance integration
- Create: `app/specs/service.py` — CRUD operations
- Create: `app/specs/router.py` — API endpoints
- Modify: `app/main.py` — include `specs.router`
- Create: `tests/test_specs_parser.py`, `tests/test_specs_router.py`

**Frontend (`frontend/`):**
- Modify: `src/api/types.ts`
- Create: `src/api/specs.ts`
- Modify: `src/pages/Dashboard.tsx` — list projects
- Create: `src/pages/ProjectDetail.tsx` — upload spec
- Create: `src/pages/SpecUpload.tsx` — upload UI component
- Create: `src/pages/EndpointExplorer.tsx` — view parsed endpoints
- Modify: `src/App.tsx` — add new routes

---

## Task 1: Add Prance and PyYAML dependencies

**Files:**
- Modify: `C:\AI_TEST_AUTOMATION\backend\pyproject.toml`

- [ ] **Step 1: Add `prance` and `openapi-spec-validator`**

In `backend/pyproject.toml`, add these to the `dependencies` list:
```toml
    "prance>=25.4",
    "openapi-spec-validator>=0.8.5",
    "pyyaml>=6",
```

- [ ] **Step 2: Install dependencies**

```bash
cd backend
pip install -e ".[dev]"
```

- [ ] **Step 3: Commit**

```bash
git add backend/pyproject.toml
git commit -m "chore(backend): add prance and openapi-spec-validator deps"
```

---

## Task 2: Database Models & Migration

**Files:**
- Modify: `C:\AI_TEST_AUTOMATION\backend\app\models.py`

- [ ] **Step 1: Add Project, Spec, Endpoint models**

In `app/models.py`, add the following models. Import `JSONB` from `sqlalchemy.dialects.postgresql` and `ForeignKey` from `sqlalchemy`.

```python
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
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
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
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
    spec_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("specs.id", ondelete="CASCADE"), index=True)
    method: Mapped[str] = mapped_column(String(10), nullable=False) # GET, POST, etc
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    summary: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    parameters: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    request_body: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    responses: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
```

- [ ] **Step 2: Generate Alembic migration**

```bash
cd backend
alembic revision --autogenerate -m "add project spec endpoint models"
```

- [ ] **Step 3: Apply migration**

```bash
alembic upgrade head
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/models.py backend/alembic/versions/
git commit -m "feat(db): add Project, Spec, and Endpoint models"
```

---

## Task 3: Pydantic Schemas

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\backend\app\specs\schemas.py`
- Create: `C:\AI_TEST_AUTOMATION\backend\app\specs\__init__.py`

- [ ] **Step 1: Create Schemas**

Write `app/specs/schemas.py`:
```python
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., max_length=255)
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
```

- [ ] **Step 2: Create __init__.py**

Create `app/specs/__init__.py` (leave empty or use for exports).

- [ ] **Step 3: Commit**

```bash
git add backend/app/specs/schemas.py backend/app/specs/__init__.py
git commit -m "feat(specs): add Pydantic schemas for projects, specs, endpoints"
```

---

## Task 4: OpenAPI Parser Logic

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\backend\app\specs\parser.py`
- Create: `C:\AI_TEST_AUTOMATION\backend\tests\test_specs_parser.py`

- [ ] **Step 1: Write Parser Tests**

Write `tests/test_specs_parser.py`:
```python
import pytest
from app.specs.parser import parse_openapi_spec

SAMPLE_SPEC = """
openapi: 3.0.0
info:
  title: Sample API
  version: 1.0.0
paths:
  /users:
    get:
      summary: List users
      responses:
        '200':
          description: OK
    post:
      summary: Create user
      requestBody:
        content:
          application/json:
            schema:
              type: object
      responses:
        '201':
          description: Created
"""

def test_parse_valid_spec():
    version, raw, endpoints = parse_openapi_spec(SAMPLE_SPEC)
    assert version == "1.0.0"
    assert len(endpoints) == 2
    
    methods = {e["method"] for e in endpoints}
    assert methods == {"get", "post"}
    
    get_ep = next(e for e in endpoints if e["method"] == "get")
    assert get_ep["path"] == "/users"
    assert get_ep["summary"] == "List users"
    
def test_parse_invalid_spec():
    with pytest.raises(ValueError):
        parse_openapi_spec("invalid yaml {")
```

- [ ] **Step 2: Implement Parser**

Write `app/specs/parser.py`:
```python
from typing import Any
import yaml
from prance import ResolvingParser
from prance.util.exceptions import ValidationError, ParseError

def parse_openapi_spec(spec_content: str | bytes) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    """
    Parses an OpenAPI spec string/bytes, resolves references, and extracts endpoints.
    Returns: (version, raw_dict, endpoints_list)
    """
    if isinstance(spec_content, bytes):
        spec_content = spec_content.decode('utf-8')
        
    try:
        # Load spec and validate/resolve using prance
        parser = ResolvingParser(spec_string=spec_content, backend='openapi-spec-validator')
    except (ValidationError, ParseError, yaml.YAMLError) as e:
        raise ValueError(f"Invalid OpenAPI specification: {str(e)}") from e

    spec_dict = parser.specification
    version = spec_dict.get("info", {}).get("version", "unknown")
    
    endpoints: list[dict[str, Any]] = []
    
    paths = spec_dict.get("paths", {})
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
            
        for method, operation in path_item.items():
            method_lower = method.lower()
            if method_lower not in ["get", "post", "put", "delete", "patch", "options", "head"]:
                continue
                
            endpoints.append({
                "method": method_lower,
                "path": path,
                "summary": operation.get("summary"),
                "parameters": operation.get("parameters", []),
                "request_body": operation.get("requestBody"),
                "responses": operation.get("responses", {})
            })
            
    return version, spec_dict, endpoints
```

- [ ] **Step 3: Run tests**
```bash
pytest tests/test_specs_parser.py -v
```
Expected: All pass.

- [ ] **Step 4: Commit**
```bash
git add backend/app/specs/parser.py backend/tests/test_specs_parser.py
git commit -m "feat(specs): add OpenAPI parsing and endpoint extraction"
```

---

## Task 5: Specs Router and Services

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\backend\app\specs\service.py`
- Create: `C:\AI_TEST_AUTOMATION\backend\app\specs\router.py`
- Modify: `C:\AI_TEST_AUTOMATION\backend\app\main.py`
- Create: `C:\AI_TEST_AUTOMATION\backend\tests\test_specs_router.py`

- [ ] **Step 1: Write Specs Service**

Write `app/specs/service.py`:
```python
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models import Project, Spec, Endpoint
from app.specs.schemas import ProjectCreate
from app.specs.parser import parse_openapi_spec


async def create_project(db: AsyncSession, user_id: uuid.UUID, payload: ProjectCreate) -> Project:
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
    result = await db.execute(select(Project).where(Project.user_id == user_id).order_by(Project.created_at.desc()))
    return list(result.scalars().all())

async def get_project(db: AsyncSession, user_id: uuid.UUID, project_id: uuid.UUID) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project

async def ingest_spec(db: AsyncSession, user_id: uuid.UUID, project_id: uuid.UUID, file_content: bytes) -> tuple[Spec, list[Endpoint]]:
    # Verify project exists and belongs to user
    await get_project(db, user_id, project_id)
    
    try:
        version, raw_dict, endpoints_data = parse_openapi_spec(file_content)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        
    spec = Spec(
        project_id=project_id,
        version=version,
        raw_content=raw_dict
    )
    db.add(spec)
    await db.flush() # Get spec.id
    
    endpoints = []
    for ep_data in endpoints_data:
        ep = Endpoint(
            spec_id=spec.id,
            method=ep_data["method"],
            path=ep_data["path"],
            summary=ep_data["summary"],
            parameters=ep_data["parameters"],
            request_body=ep_data["request_body"],
            responses=ep_data["responses"]
        )
        db.add(ep)
        endpoints.append(ep)
        
    await db.commit()
    await db.refresh(spec)
    return spec, endpoints

async def get_specs(db: AsyncSession, project_id: uuid.UUID) -> list[Spec]:
    result = await db.execute(select(Spec).where(Spec.project_id == project_id).order_by(Spec.created_at.desc()))
    return list(result.scalars().all())

async def get_endpoints(db: AsyncSession, spec_id: uuid.UUID) -> list[Endpoint]:
    result = await db.execute(select(Endpoint).where(Endpoint.spec_id == spec_id).order_by(Endpoint.path, Endpoint.method))
    return list(result.scalars().all())
```

- [ ] **Step 2: Write Specs Router**

Write `app/specs/router.py`:
```python
from __future__ import annotations
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import CurrentUser, DbSession
from app.specs.schemas import ProjectCreate, ProjectRead, SpecRead, EndpointRead
from app.specs import service

router = APIRouter()

@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(payload: ProjectCreate, user: CurrentUser, db: DbSession):
    return await service.create_project(db, user.id, payload)

@router.get("/projects", response_model=list[ProjectRead])
async def list_projects(user: CurrentUser, db: DbSession):
    return await service.get_projects(db, user.id)

@router.get("/projects/{project_id}", response_model=ProjectRead)
async def get_project(project_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return await service.get_project(db, user.id, project_id)

@router.post("/projects/{project_id}/specs", response_model=SpecRead, status_code=status.HTTP_201_CREATED)
async def upload_spec(project_id: uuid.UUID, file: UploadFile, user: CurrentUser, db: DbSession):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    spec, _ = await service.ingest_spec(db, user.id, project_id, content)
    return spec

@router.get("/projects/{project_id}/specs", response_model=list[SpecRead])
async def list_specs(project_id: uuid.UUID, user: CurrentUser, db: DbSession):
    # Verify project
    await service.get_project(db, user.id, project_id)
    return await service.get_specs(db, project_id)

@router.get("/specs/{spec_id}/endpoints", response_model=list[EndpointRead])
async def list_endpoints(spec_id: uuid.UUID, user: CurrentUser, db: DbSession):
    # In a fully robust system we'd verify spec -> project -> user.id here. 
    # For POC, spec ID is UUID so reasonably unguessable, but let's be safe.
    from app.models import Spec, Project
    from sqlalchemy import select
    
    stmt = select(Spec).join(Project).where(Spec.id == spec_id, Project.user_id == user.id)
    result = await db.execute(stmt)
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Spec not found")
        
    return await service.get_endpoints(db, spec_id)
```

- [ ] **Step 3: Wire router in `main.py`**

In `app/main.py`, under the auth router include:
```python
    from app.specs.router import router as specs_router
    app.include_router(specs_router, prefix="/api/v1", tags=["specs"])
```

- [ ] **Step 4: Run tests**

Write `tests/test_specs_router.py`:
```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_and_get_project(auth_client: AsyncClient):
    # Create project
    resp = await auth_client.post("/api/v1/projects", json={
        "name": "Test Project",
        "description": "A project for testing"
    })
    assert resp.status_code == 201
    project_id = resp.json()["id"]
    
    # Get project
    resp = await auth_client.get(f"/api/v1/projects/{project_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test Project"
```

```bash
pytest -v tests/test_specs_router.py
```

- [ ] **Step 5: Commit**
```bash
git add backend/app/specs/service.py backend/app/specs/router.py backend/app/main.py
git commit -m "feat(specs): add router and service for projects, specs, endpoints"
```

---

## Task 6: Frontend API updates

**Files:**
- Modify: `C:\AI_TEST_AUTOMATION\frontend\src\api\types.ts`
- Create: `C:\AI_TEST_AUTOMATION\frontend\src\api\specs.ts`

- [ ] **Step 1: Add types**

In `frontend/src/api/types.ts`:
```ts
export interface Project {
  id: string;
  name: string;
  description: string | null;
  target_base_url: string | null;
  created_at: string;
}

export interface Spec {
  id: string;
  project_id: string;
  version: string;
  parsed_at: string;
  created_at: string;
}

export interface Endpoint {
  id: string;
  spec_id: string;
  method: string;
  path: string;
  summary: string | null;
  parameters: any[] | null;
  request_body: any | null;
  responses: any | null;
}
```

- [ ] **Step 2: Add API functions**

Write `frontend/src/api/specs.ts`:
```ts
import { apiClient } from "./client";
import type { Project, Spec, Endpoint } from "./types";

export async function createProject(payload: { name: string; description?: string; target_base_url?: string }): Promise<Project> {
  const { data } = await apiClient.post<Project>("/projects", payload);
  return data;
}

export async function getProjects(): Promise<Project[]> {
  const { data } = await apiClient.get<Project[]>("/projects");
  return data;
}

export async function getProject(projectId: string): Promise<Project> {
  const { data } = await apiClient.get<Project>(`/projects/${projectId}`);
  return data;
}

export async function uploadSpec(projectId: string, file: File): Promise<Spec> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await apiClient.post<Spec>(`/projects/${projectId}/specs`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function getSpecs(projectId: string): Promise<Spec[]> {
  const { data } = await apiClient.get<Spec[]>(`/projects/${projectId}/specs`);
  return data;
}

export async function getEndpoints(specId: string): Promise<Endpoint[]> {
  const { data } = await apiClient.get<Endpoint[]>(`/specs/${specId}/endpoints`);
  return data;
}
```

- [ ] **Step 3: Commit**
```bash
git add frontend/src/api/types.ts frontend/src/api/specs.ts
git commit -m "feat(frontend): add specs api client functions"
```

---

## Task 7: Frontend UI - Dashboard (Projects list)

**Files:**
- Modify: `C:\AI_TEST_AUTOMATION\frontend\src\pages\Dashboard.tsx`

- [ ] **Step 1: Implement Dashboard**

Update `Dashboard.tsx` to fetch and list projects using `useQuery` from `@tanstack/react-query`, and include a simple form to create a new project. 

```tsx
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { getProjects, createProject } from "../api/specs";

export function Dashboard() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const { data: projects, isLoading } = useQuery({ queryKey: ["projects"], queryFn: getProjects });
  
  const createMutation = useMutation({
    mutationFn: createProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setName("");
    }
  });

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-4">Projects</h1>
      <div className="mb-8">
        <input className="border p-2 mr-2" value={name} onChange={e => setName(e.target.value)} placeholder="Project Name" />
        <button className="bg-blue-500 text-white p-2" onClick={() => createMutation.mutate({ name })}>Create Project</button>
      </div>
      {isLoading ? <p>Loading...</p> : (
        <ul>
          {projects?.map(p => (
            <li key={p.id} className="mb-2"><Link className="text-blue-600 underline" to={`/projects/${p.id}`}>{p.name}</Link></li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**
```bash
git add frontend/src/pages/Dashboard.tsx
git commit -m "feat(frontend): Dashboard lists projects and allows creation"
```

---

## Task 8: Frontend UI - ProjectDetail & EndpointExplorer

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\frontend\src\pages\ProjectDetail.tsx`
- Create: `C:\AI_TEST_AUTOMATION\frontend\src\pages\EndpointExplorer.tsx`
- Modify: `C:\AI_TEST_AUTOMATION\frontend\src\App.tsx`

- [ ] **Step 1: Implement ProjectDetail and Spec Upload**
Create a view that loads a specific project, lists its specs, and has a file input to upload a new OpenAPI spec (YAML/JSON). 

Write `src/pages/ProjectDetail.tsx`:
```tsx
import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getProject, getSpecs, uploadSpec } from "../api/specs";

export function ProjectDetail() {
  const { projectId } = useParams<{ projectId: string }>();
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);

  const { data: project } = useQuery({ queryKey: ["projects", projectId], queryFn: () => getProject(projectId!) });
  const { data: specs } = useQuery({ queryKey: ["specs", projectId], queryFn: () => getSpecs(projectId!) });

  const uploadMutation = useMutation({
    mutationFn: (f: File) => uploadSpec(projectId!, f),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["specs", projectId] });
      setFile(null);
    }
  });

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-4">{project?.name} - Specs</h1>
      <div className="mb-8 border p-4">
        <input type="file" onChange={e => setFile(e.target.files?.[0] || null)} />
        <button className="bg-blue-500 text-white p-2 ml-2" onClick={() => file && uploadMutation.mutate(file)}>Upload Spec</button>
      </div>
      <ul>
        {specs?.map(s => (
          <li key={s.id} className="mb-2">
            Spec version {s.version} - <Link className="text-blue-600 underline" to={`/specs/${s.id}/endpoints`}>View Endpoints</Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 2: Implement EndpointExplorer**
Create a view that takes a `specId` from the URL, fetches the endpoints for that spec, and displays them.

Write `src/pages/EndpointExplorer.tsx`:
```tsx
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getEndpoints } from "../api/specs";

export function EndpointExplorer() {
  const { specId } = useParams<{ specId: string }>();
  const { data: endpoints, isLoading } = useQuery({ queryKey: ["endpoints", specId], queryFn: () => getEndpoints(specId!) });

  if (isLoading) return <p className="p-8">Loading...</p>;

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-4">Endpoints</h1>
      <table className="w-full border-collapse border border-gray-300">
        <thead>
          <tr className="bg-gray-100">
            <th className="border p-2">Method</th>
            <th className="border p-2">Path</th>
            <th className="border p-2">Summary</th>
          </tr>
        </thead>
        <tbody>
          {endpoints?.map(ep => (
            <tr key={ep.id}>
              <td className="border p-2 font-mono uppercase">{ep.method}</td>
              <td className="border p-2 font-mono">{ep.path}</td>
              <td className="border p-2">{ep.summary}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 3: Update App.tsx**
Add the new routes:
```tsx
<Route path="/projects/:projectId" element={<ProtectedRoute><ProjectDetail /></ProtectedRoute>} />
<Route path="/specs/:specId/endpoints" element={<ProtectedRoute><EndpointExplorer /></ProtectedRoute>} />
```

- [ ] **Step 4: Verify Full Flow**
1. Run backend and frontend
2. Log in
3. Create project
4. Upload `C:\AI_TEST_AUTOMATION\sample-api\openapi.json` or download a vampi spec.
5. See endpoints listed.

- [ ] **Step 5: Commit**
```bash
git add frontend/src/pages/ProjectDetail.tsx frontend/src/pages/EndpointExplorer.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add project detail and endpoint explorer views"
```

---

## Verification Checklist (end of Week 2)

- [ ] Database contains `projects`, `specs`, and `endpoints` tables.
- [ ] Spec ingestion handles YAML and JSON OpenAPI specs.
- [ ] Endpoint extraction correctly pulls method, path, and parameters.
- [ ] Frontend successfully uploads files to backend.
- [ ] Frontend displays extracted endpoints.
- [ ] `pytest -v` — all green
- [ ] `ruff check .` — clean
- [ ] `mypy app` — clean
- [ ] `npm run build` succeeds in `frontend/`

When all 9 boxes are ticked, you are done with Week 2.

---

## Notes for Week 3

In Week 3, we will use LiteLLM to generate functional tests using structured output and save them directly as JSON to the database. The `EndpointExplorer` will be augmented with test generation controls.
