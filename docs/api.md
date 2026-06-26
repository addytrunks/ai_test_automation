# API Reference

> AI-Assisted API Test Generation Platform — REST API Overview

All endpoints are prefixed with `/api/v1`. Protected endpoints require a JWT Bearer token in the `Authorization` header.

---

## Authentication

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/auth/register` | — | Create a new user account |
| `POST` | `/auth/login` | — | Authenticate and receive a JWT access token |
| `GET` | `/auth/me` | 🔒 | Get the authenticated user's profile |

### Register
```
POST /api/v1/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword",
  "name": "Test User"
}

→ 201 Created
{
  "id": "uuid",
  "email": "user@example.com",
  "name": "Test User",
  "created_at": "2026-05-14T10:00:00Z"
}
```

### Login
```
POST /api/v1/auth/login
Content-Type: application/x-www-form-urlencoded

username=user@example.com&password=securepassword

→ 200 OK
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

---

## Projects

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/projects` | 🔒 | Create a new project |
| `GET` | `/projects` | 🔒 | List all projects for the authenticated user |
| `GET` | `/projects/{project_id}` | 🔒 | Get a specific project |
| `PATCH` | `/projects/{project_id}` | 🔒 | Update project details |
| `DELETE` | `/projects/{project_id}` | 🔒 | Delete a project and all associated data |

### Create Project
```
POST /api/v1/projects
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "VAmPI Testing",
  "description": "Security testing for VAmPI API",
  "target_base_url": "http://localhost:5001"
}

→ 201 Created
```

---

## Specs & Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/projects/{project_id}/specs` | 🔒 | Upload and parse an OpenAPI spec (JSON body) |
| `GET` | `/projects/{project_id}/specs` | 🔒 | List specs for a project |
| `GET` | `/specs/{spec_id}/endpoints` | 🔒 | List parsed endpoints for a spec |

### Upload Spec
```
POST /api/v1/projects/{project_id}/specs
Authorization: Bearer <token>
Content-Type: application/json

{
  "openapi": "3.0.0",
  "info": { "title": "VAmPI", "version": "1.0" },
  "paths": { ... }
}

→ 201 Created
{
  "id": "uuid",
  "version": "3.0.0",
  "parsed_at": "2026-05-20T12:00:00Z",
  "endpoints": [
    {
      "id": "uuid",
      "method": "GET",
      "path": "/users/v1",
      "summary": "List users"
    }
  ]
}
```

---

## Test Suites & Tests

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/projects/{project_id}/test-suites/generate` | 🔒 | Generate a test suite via LLM |
| `GET` | `/projects/{project_id}/test-suites` | 🔒 | List test suites for a project |
| `GET` | `/test-suites/{suite_id}` | 🔒 | Get test suite details |
| `GET` | `/test-suites/{suite_id}/tests` | 🔒 | List all tests in a suite |
| `DELETE` | `/test-suites/{suite_id}` | 🔒 | Delete a test suite |

### Generate Test Suite
```
POST /api/v1/projects/{project_id}/test-suites/generate
Authorization: Bearer <token>
Content-Type: application/json

{
  "spec_id": "uuid",
  "name": "Security Tests v1",
  "auto_loop_enabled": true,
  "auto_loop_max_depth": 3,
  "auto_loop_max_tests_per_cycle": 5
}

→ 201 Created
{
  "id": "uuid",
  "name": "Security Tests v1",
  "status": "generated",
  "test_count": 15
}
```

---

## Runs & Execution

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/test-suites/{suite_id}/runs` | 🔒 | Execute tests (optionally with agentic loop) |
| `GET` | `/test-suites/{suite_id}/runs` | 🔒 | List runs for a test suite |
| `GET` | `/runs/{run_id}` | 🔒 | Get run details and summary |
| `GET` | `/runs/{run_id}/results` | 🔒 | Get individual test results for a run |

### Start a Run
```
POST /api/v1/test-suites/{suite_id}/runs
Authorization: Bearer <token>
Content-Type: application/json

{
  "target_base_url": "http://localhost:5001"
}

→ 201 Created
{
  "id": "uuid",
  "status": "running",
  "loop_iteration": 0
}
```

### Run Summary
```
GET /api/v1/runs/{run_id}

→ 200 OK
{
  "id": "uuid",
  "status": "completed",
  "loop_iteration": 2,
  "summary": {
    "total": 15,
    "passed": 10,
    "failed": 4,
    "errors": 1
  },
  "started_at": "2026-06-01T10:00:00Z",
  "completed_at": "2026-06-01T10:02:30Z"
}
```

---

## Analysis & Coverage

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/test-results/{result_id}/analysis` | 🔒 | Get AI analysis for a failed test |
| `GET` | `/runs/{run_id}/gaps` | 🔒 | Get coverage gaps discovered in a run |
| `GET` | `/test-suites/{suite_id}/gaps` | 🔒 | Get all coverage gaps for a test suite |
| `POST` | `/test-suites/{suite_id}/coverage-analyze` | 🔒 | Trigger coverage analysis for a suite |

### Coverage Gap Response
```
GET /api/v1/runs/{run_id}/gaps

→ 200 OK
[
  {
    "id": "uuid",
    "endpoint_id": "uuid",
    "scenario_description": "No BOLA test exists for GET /users/v1/{username}",
    "severity": "HIGH",
    "spawned_test_id": "uuid"
  }
]
```

### AI Analysis Response
```
GET /api/v1/test-results/{result_id}/analysis

→ 200 OK
{
  "id": "uuid",
  "test_result_id": "uuid",
  "explanation": "The test expected status 401 but received 200...",
  "likely_cause": "The endpoint does not enforce authentication...",
  "suggested_fix": "Add authentication middleware to the endpoint..."
}
```

---

## Health

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | — | Service health check |

```
GET /api/v1/health
→ 200 OK
{ "status": "ok" }
```

---

## Error Responses

All error responses follow a consistent format:

```json
{
  "detail": "Human-readable error message"
}
```

| Status Code | Meaning |
|---|---|
| `400` | Bad Request — invalid input data |
| `401` | Unauthorized — missing or invalid JWT |
| `403` | Forbidden — authenticated but not authorized for this resource |
| `404` | Not Found — resource does not exist or belongs to another user |
| `422` | Validation Error — request body failed Pydantic validation |
| `500` | Internal Server Error — unexpected failure |
