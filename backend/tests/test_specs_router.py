import pytest
from httpx import AsyncClient

SAMPLE_SPEC_YAML = b"""
openapi: 3.0.0
info:
  title: Test API
  version: 2.0.0
paths:
  /items:
    get:
      summary: List items
      responses:
        '200':
          description: OK
    post:
      summary: Create item
      requestBody:
        content:
          application/json:
            schema:
              type: object
      responses:
        '201':
          description: Created
"""


@pytest.mark.asyncio
async def test_create_and_get_project(auth_client: AsyncClient) -> None:
    # Create project
    resp = await auth_client.post(
        "/api/v1/projects",
        json={"name": "Test Project", "description": "A project for testing"},
    )
    assert resp.status_code == 201
    project = resp.json()
    assert project["name"] == "Test Project"
    assert project["description"] == "A project for testing"
    project_id = project["id"]

    # Get project
    resp = await auth_client.get(f"/api/v1/projects/{project_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test Project"


@pytest.mark.asyncio
async def test_list_projects(auth_client: AsyncClient) -> None:
    await auth_client.post("/api/v1/projects", json={"name": "Project A"})
    await auth_client.post("/api/v1/projects", json={"name": "Project B"})

    resp = await auth_client.get("/api/v1/projects")
    assert resp.status_code == 200
    projects = resp.json()
    assert len(projects) >= 2
    names = {p["name"] for p in projects}
    assert "Project A" in names
    assert "Project B" in names


@pytest.mark.asyncio
async def test_get_nonexistent_project(auth_client: AsyncClient) -> None:
    resp = await auth_client.get("/api/v1/projects/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_projects_require_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/projects")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_project(auth_client: AsyncClient) -> None:
    # Create project
    resp = await auth_client.post(
        "/api/v1/projects",
        json={"name": "Original Name", "description": "Original desc"},
    )
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    # Update only the name (partial update)
    resp = await auth_client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "Updated Name"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"
    assert resp.json()["description"] == "Original desc"  # unchanged


@pytest.mark.asyncio
async def test_delete_project(auth_client: AsyncClient) -> None:
    # Create project
    resp = await auth_client.post("/api/v1/projects", json={"name": "To Delete"})
    project_id = resp.json()["id"]

    # Delete it
    resp = await auth_client.delete(f"/api/v1/projects/{project_id}")
    assert resp.status_code == 204

    # Verify it's gone
    resp = await auth_client.get(f"/api/v1/projects/{project_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_project_cascades_specs(auth_client: AsyncClient) -> None:
    # Create project + upload spec
    resp = await auth_client.post("/api/v1/projects", json={"name": "Cascade Test"})
    project_id = resp.json()["id"]

    resp = await auth_client.post(
        f"/api/v1/projects/{project_id}/specs",
        files={"file": ("openapi.yaml", SAMPLE_SPEC_YAML, "application/x-yaml")},
    )
    spec_id = resp.json()["id"]

    # Delete project — should cascade to specs and endpoints
    resp = await auth_client.delete(f"/api/v1/projects/{project_id}")
    assert resp.status_code == 204

    # Verify endpoints for that spec are also gone
    resp = await auth_client.get(f"/api/v1/specs/{spec_id}/endpoints")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upload_and_list_specs(auth_client: AsyncClient) -> None:
    # Create project first
    resp = await auth_client.post("/api/v1/projects", json={"name": "Spec Test"})
    project_id = resp.json()["id"]

    # Upload spec
    resp = await auth_client.post(
        f"/api/v1/projects/{project_id}/specs",
        files={"file": ("openapi.yaml", SAMPLE_SPEC_YAML, "application/x-yaml")},
    )
    assert resp.status_code == 201
    spec = resp.json()
    assert spec["version"] == "2.0.0"
    assert spec["project_id"] == project_id

    # List specs
    resp = await auth_client.get(f"/api/v1/projects/{project_id}/specs")
    assert resp.status_code == 200
    specs = resp.json()
    assert len(specs) == 1


@pytest.mark.asyncio
async def test_list_endpoints(auth_client: AsyncClient) -> None:
    # Create project + upload spec
    resp = await auth_client.post("/api/v1/projects", json={"name": "Endpoint Test"})
    project_id = resp.json()["id"]

    resp = await auth_client.post(
        f"/api/v1/projects/{project_id}/specs",
        files={"file": ("openapi.yaml", SAMPLE_SPEC_YAML, "application/x-yaml")},
    )
    spec_id = resp.json()["id"]

    # List endpoints
    resp = await auth_client.get(f"/api/v1/specs/{spec_id}/endpoints")
    assert resp.status_code == 200
    endpoints = resp.json()
    assert len(endpoints) == 2
    methods = {ep["method"] for ep in endpoints}
    assert methods == {"get", "post"}
    paths = {ep["path"] for ep in endpoints}
    assert "/items" in paths


@pytest.mark.asyncio
async def test_upload_invalid_spec(auth_client: AsyncClient) -> None:
    resp = await auth_client.post("/api/v1/projects", json={"name": "Bad Spec Test"})
    project_id = resp.json()["id"]

    resp = await auth_client.post(
        f"/api/v1/projects/{project_id}/specs",
        files={"file": ("bad.yaml", b"not valid openapi {{{", "application/x-yaml")},
    )
    assert resp.status_code == 400
