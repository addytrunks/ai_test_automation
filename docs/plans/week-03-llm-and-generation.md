# Week 3 Implementation Plan — LLM & Generation

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the LLM layer using LiteLLM and build the prompt generator. Allow users to select an endpoint, choose scenario types, and generate structured JSON test cases that are saved to the database. Provide a read-only UI to view the generated tests.

**Architecture:** We will add `test_suites` and `tests` tables. The `llm` module wraps LiteLLM to be provider-agnostic. The `generator` module reads few-shot patterns (`patterns/*.yaml`), constructs a prompt, uses structured output (`response_format` in Pydantic) to get test cases, validates them against the endpoint parameters, and saves them. The UI adds test suite creation and a JSON-based test viewer.

**Tech Stack Additions:** `litellm`. React component `react-json-view-lite` for displaying JSON test bodies and assertions.

**Verification gate:** You can click on the `GET /users` endpoint, select "positive" and "negative" scenarios, click Generate, and within ~10 seconds see 5-10 structured test cases in the UI (method, path, headers, body, assertions).

---

## File Structure for Week 3

**Backend (`backend/`):**
- Modify: `app/models.py` — add TestSuite, Test
- Add migration: `alembic/versions/..._add_test_models.py`
- Create: `app/llm/__init__.py`, `app/llm/client.py`
- Create: `app/generator/__init__.py`, `app/generator/router.py`, `app/generator/service.py`, `app/generator/schemas.py`, `app/generator/prompts.py`
- Create: `app/generator/patterns/` directory containing `positive.yaml`, `negative.yaml`, `auth_bypass.yaml`, `bola.yaml`, `boundary.yaml`, `injection.yaml`
- Modify: `app/main.py` — include `generator.router`
- Create: `tests/test_llm.py`, `tests/test_generator.py`

**Frontend (`frontend/`):**
- Modify: `src/api/types.ts`
- Create: `src/api/generator.ts`
- Create: `src/pages/TestSuiteDetail.tsx` — View test suites and their tests
- Modify: `src/pages/EndpointExplorer.tsx` — Add "Generate Tests" button/form
- Create: `src/components/TestCard.tsx` — Component to display test info and `react-json-view-lite`
- Modify: `src/App.tsx` — Add routes

---

## Task 1: LiteLLM setup and dependencies

**Files:**
- Modify: `C:\AI_TEST_AUTOMATION\backend\pyproject.toml`
- Modify: `C:\AI_TEST_AUTOMATION\frontend\package.json`

- [ ] **Step 1: Add dependencies**

Backend `pyproject.toml` `dependencies`:
```toml
    "litellm>=1.84.0",
```

Frontend:
```bash
cd frontend
npm install react-json-view-lite
```

- [ ] **Step 2: Install**
```bash
cd backend
pip install -e ".[dev]"
```

- [ ] **Step 3: Commit**
```bash
git add backend/pyproject.toml frontend/package.json frontend/package-lock.json
git commit -m "chore: add litellm and react-json-view-lite deps"
```

---

## Task 2: Database Models & Migration

**Files:**
- Modify: `C:\AI_TEST_AUTOMATION\backend\app\models.py`

- [ ] **Step 1: Add TestSuite and Test models**

In `app/models.py`, add:

```python
from sqlalchemy import Boolean, Integer

class TestSuite(Base):
    __tablename__ = "test_suites"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    spec_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("specs.id", ondelete="CASCADE"), index=True)
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
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

class Test(Base):
    __tablename__ = "tests"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        primary_key=True,
        default=uuid.uuid4,
    )
    test_suite_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_suites.id", ondelete="CASCADE"), index=True)
    endpoint_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("endpoints.id", ondelete="CASCADE"), index=True)
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    scenario_type: Mapped[str] = mapped_column(String(50), nullable=False) # positive/negative/security
    
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    path_params: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    query_params: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    headers: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    body: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    
    expected_status: Mapped[int] = mapped_column(Integer, nullable=False)
    assertions: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    
    auto_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    parent_coverage_gap_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"), nullable=True)
    generation_depth: Mapped[int] = mapped_column(Integer, default=0)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
```

- [ ] **Step 2: Generate Alembic migration**
```bash
cd backend
alembic revision --autogenerate -m "add test models"
alembic upgrade head
```

- [ ] **Step 3: Commit**
```bash
git add backend/app/models.py backend/alembic/versions/
git commit -m "feat(db): add TestSuite and Test models"
```

---

## Task 3: LLM Layer

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\backend\app\llm\__init__.py`
- Create: `C:\AI_TEST_AUTOMATION\backend\app\llm\client.py`

- [ ] **Step 1: Write LLM Client**

Write `app/llm/client.py`:
```python
from typing import Any, Type, TypeVar
import litellm
from pydantic import BaseModel
from app.config import get_settings

T = TypeVar("T", bound=BaseModel)

async def generate_structured(
    prompt: str,
    response_model: Type[T],
    system_prompt: str = "You are a helpful assistant.",
    temperature: float = 0.1
) -> T:
    """
    Calls the LLM specified in config and returns a structured Pydantic object.
    Uses litellm to abstract the provider.
    """
    settings = get_settings()
    
    # Configure litellm api key based on provider
    if settings.llm_model.startswith("openai/"):
        litellm.api_key = settings.openai_api_key
        
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]
    
    # LiteLLM supports passing a pydantic model to response_format for models that support structured outputs
    try:
        response = await litellm.acompletion(
            model=settings.llm_model,
            messages=messages,
            response_format=response_model,
            temperature=temperature
        )
        # Parse the response string back into the pydantic model
        content = response.choices[0].message.content
        return response_model.model_validate_json(content)
    except Exception as e:
        # In a real app, wrap and log
        raise RuntimeError(f"LLM generation failed: {str(e)}") from e
```

- [ ] **Step 2: Commit**
```bash
git add backend/app/llm/
git commit -m "feat(llm): add litellm wrapper for structured output"
```

---

## Task 4: Generator Pydantic Schemas and Patterns

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\backend\app\generator\__init__.py`
- Create: `C:\AI_TEST_AUTOMATION\backend\app\generator\schemas.py`
- Create: `C:\AI_TEST_AUTOMATION\backend\app\generator\patterns\positive.yaml`

- [ ] **Step 1: Create Generator Schemas**

Write `app/generator/schemas.py`:
```python
from __future__ import annotations
import uuid
from typing import Any, Literal
from pydantic import BaseModel, Field

class AssertionSchema(BaseModel):
    type: Literal["status_eq", "json_path", "body_contains", "header_eq", "response_time_lt"]
    target: str | None = None
    op: str | None = None
    expected: Any | None = None

class GeneratedTestSchema(BaseModel):
    name: str = Field(description="Short descriptive name for the test")
    description: str = Field(description="Detailed explanation of what the test verifies")
    scenario_type: Literal["positive", "negative", "auth_bypass", "bola", "boundary", "injection"]
    
    path_params: dict[str, Any] | None = Field(default=None, description="Path parameters to inject")
    query_params: dict[str, Any] | None = Field(default=None, description="Query string parameters")
    headers: dict[str, Any] | None = Field(default=None, description="HTTP headers")
    body: dict[str, Any] | None = Field(default=None, description="JSON request body")
    
    expected_status: int = Field(description="Expected HTTP status code")
    assertions: list[AssertionSchema] = Field(description="List of assertions to run against response")

class TestSuiteCreate(BaseModel):
    name: str
    spec_id: uuid.UUID
    endpoint_ids: list[uuid.UUID]
    scenarios: list[str] = ["positive", "negative"]

class TestSuiteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    spec_id: uuid.UUID
    name: str
    status: str
    created_at: Any
    updated_at: Any
    
class TestRead(BaseModel):
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
```

Create `app/generator/patterns/positive.yaml` and the remaining 5 pattern files:
```yaml
description: "Generate standard positive functional tests with valid inputs."
examples:
  - input: "Endpoint path: /users, method: post, params: none, body: {email: string, age: int}"
    output:
      name: "Create user with valid data"
      description: "Verifies user can be created when providing valid email and age"
      scenario_type: "positive"
      body: {"email": "test@example.com", "age": 25}
      expected_status: 201
      assertions:
        - {type: "status_eq", expected: 201}
        - {type: "json_path", target: "$.id", op: "exists"}
```
*(Agent must also create `negative.yaml`, `auth_bypass.yaml`, `bola.yaml`, `boundary.yaml`, `injection.yaml` following the same structure, adapting the description and examples for each scenario type).*

- [ ] **Step 3: Commit**
```bash
git add backend/app/generator/schemas.py backend/app/generator/patterns/
git commit -m "feat(generator): add generation schemas and patterns"
```

---

## Task 5: Prompt Construction and Generation Service

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\backend\app\generator\prompts.py`
- Create: `C:\AI_TEST_AUTOMATION\backend\app\generator\service.py`

- [ ] **Step 1: Write Prompts**

Write `app/generator/prompts.py`:
```python
import yaml
import os

def load_patterns(scenarios: list[str]) -> str:
    patterns_text = ""
    base_dir = os.path.dirname(__file__)
    for scenario in scenarios:
        path = os.path.join(base_dir, "patterns", f"{scenario}.yaml")
        if os.path.exists(path):
            with open(path, "r") as f:
                content = yaml.safe_load(f)
                patterns_text += f"\nScenario Type: {scenario}\nDescription: {content.get('description', '')}\nExamples:\n{yaml.dump(content.get('examples', []))}\n"
    return patterns_text

def build_generation_prompt(endpoint_dict: dict, scenarios: list[str]) -> str:
    prompt = "Generate test cases for the following API endpoint.\n\n"
    prompt += f"Endpoint details:\n{endpoint_dict}\n\n"
    prompt += f"Requested scenario types: {', '.join(scenarios)}\n\n"
    prompt += "Instructions:\n"
    prompt += "- Ensure path_params match the variables in the path (e.g. {id}).\n"
    prompt += "- Include appropriate headers (like Content-Type: application/json).\n"
    prompt += "- Include at least one 'status_eq' assertion.\n\n"
    prompt += "Use the following patterns as examples for generating the tests:\n"
    prompt += load_patterns(scenarios)
    
    return prompt
```

- [ ] **Step 2: Write Service**

Write `app/generator/service.py`:
```python
import uuid
from typing import Any
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.models import TestSuite, Test, Endpoint, Project, Spec
from app.generator.schemas import TestSuiteCreate, GeneratedTestSchema
from app.llm.client import generate_structured
from app.generator.prompts import build_generation_prompt

# Pydantic model for a list of tests returned by LLM
from pydantic import BaseModel
class TestListResult(BaseModel):
    tests: list[GeneratedTestSchema]

async def _generate_for_endpoint(db: AsyncSession, suite_id: uuid.UUID, endpoint: Endpoint, scenarios: list[str]):
    # Convert endpoint to dict for prompt
    ep_dict = {
        "method": endpoint.method,
        "path": endpoint.path,
        "summary": endpoint.summary,
        "parameters": endpoint.parameters,
        "request_body": endpoint.request_body,
        "responses": endpoint.responses
    }
    
    prompt = build_generation_prompt(ep_dict, scenarios)
    
    # Call LLM
    result = await generate_structured(
        prompt=prompt,
        response_model=TestListResult,
        system_prompt="You are an expert API QA engineer. Generate comprehensive tests.",
        temperature=0.3
    )
    
    # Validate tests against endpoint (basic path check)
    valid_tests = []
    for t_data in result.tests:
        if "{" in endpoint.path and not t_data.path_params:
            continue # Invalid, missing path params
        valid_tests.append(t_data)
        
    # Save tests
    for t_data in valid_tests:
        test_obj = Test(
            test_suite_id=suite_id,
            endpoint_id=endpoint.id,
            name=t_data.name,
            description=t_data.description,
            scenario_type=t_data.scenario_type,
            method=endpoint.method,
            path=endpoint.path,
            path_params=t_data.path_params,
            query_params=t_data.query_params,
            headers=t_data.headers,
            body=t_data.body,
            expected_status=t_data.expected_status,
            assertions=[a.model_dump(exclude_none=True) for a in t_data.assertions]
        )
        db.add(test_obj)

async def generate_test_suite_task(suite_id: uuid.UUID, endpoint_ids: list[uuid.UUID], scenarios: list[str]):
    # This runs in a BackgroundTask. Need fresh DB session.
    from app.db import get_sessionmaker
    SessionLocal = get_sessionmaker()
    
    async with SessionLocal() as db:
        suite = await db.scalar(select(TestSuite).where(TestSuite.id == suite_id))
        if not suite:
            return
            
        suite.status = "generating"
        await db.commit()
        
        try:
            for ep_id in endpoint_ids:
                endpoint = await db.scalar(select(Endpoint).where(Endpoint.id == ep_id))
                if endpoint:
                    await _generate_for_endpoint(db, suite_id, endpoint, scenarios)
                    
            suite.status = "ready"
        except Exception as e:
            import logging
            logging.error(f"Generation failed for suite {suite_id}: {e}")
            suite.status = "error"
            
        await db.commit()

async def create_test_suite(db: AsyncSession, project_id: uuid.UUID, payload: TestSuiteCreate, background_tasks) -> TestSuite:
    suite = TestSuite(
        project_id=project_id,
        spec_id=payload.spec_id,
        name=payload.name,
        status="pending"
    )
    db.add(suite)
    await db.commit()
    await db.refresh(suite)
    
    # Kick off background generation
    from fastapi import BackgroundTasks
    background_tasks.add_task(generate_test_suite_task, suite.id, payload.endpoint_ids, payload.scenarios)
    
    return suite

async def get_test_suites(db: AsyncSession, project_id: uuid.UUID) -> list[TestSuite]:
    result = await db.execute(select(TestSuite).where(TestSuite.project_id == project_id))
    return list(result.scalars().all())

async def get_tests(db: AsyncSession, suite_id: uuid.UUID) -> list[Test]:
    result = await db.execute(select(Test).where(Test.test_suite_id == suite_id))
    return list(result.scalars().all())
```

- [ ] **Step 3: Commit**
```bash
git add backend/app/generator/prompts.py backend/app/generator/service.py
git commit -m "feat(generator): add generation service and prompt building"
```

---

## Task 6: Generator Router

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\backend\app\generator\router.py`
- Modify: `C:\AI_TEST_AUTOMATION\backend\app\main.py`

- [ ] **Step 1: Write Generator Router**

Write `app/generator/router.py`:
```python
from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import CurrentUser, DbSession
from app.generator.schemas import TestSuiteCreate, TestSuiteRead, TestRead
from app.generator import service

router = APIRouter()

@router.post("/projects/{project_id}/test-suites", response_model=TestSuiteRead, status_code=status.HTTP_201_CREATED)
async def create_suite(project_id: uuid.UUID, payload: TestSuiteCreate, background_tasks: BackgroundTasks, user: CurrentUser, db: DbSession):
    # Verify project belongs to user omitted for brevity, assume valid
    return await service.create_test_suite(db, project_id, payload, background_tasks)

@router.get("/projects/{project_id}/test-suites", response_model=list[TestSuiteRead])
async def list_suites(project_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return await service.get_test_suites(db, project_id)

@router.get("/test-suites/{suite_id}/tests", response_model=list[TestRead])
async def list_tests(suite_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return await service.get_tests(db, suite_id)
```

- [ ] **Step 2: Wire router in `main.py`**
In `app/main.py`:
```python
    from app.generator.router import router as generator_router
    app.include_router(generator_router, prefix="/api/v1", tags=["generator"])
```

- [ ] **Step 3: Commit**
```bash
git add backend/app/generator/router.py backend/app/main.py
git commit -m "feat(generator): add router for generating and viewing tests"
```

---

## Task 7: Frontend UI - Generation trigger & Test viewer

**Files:**
- Modify: `C:\AI_TEST_AUTOMATION\frontend\src\pages\EndpointExplorer.tsx`
- Create: `C:\AI_TEST_AUTOMATION\frontend\src\pages\TestSuiteDetail.tsx`
- Create: `C:\AI_TEST_AUTOMATION\frontend\src\components\TestCard.tsx`

- [ ] **Step 1: Update API client**
Add `generator.ts` functions for `createTestSuite`, `getTestSuites`, `getTests`.

- [ ] **Step 2: Endpoint Explorer Form**
In `EndpointExplorer.tsx`, add a checkbox selection for endpoints and a "Generate Tests" button. This POSTs to `/test-suites`.

- [ ] **Step 3: TestCard Component**
Build `TestCard.tsx` to display a single test using `react-json-view-lite` for the `headers`, `body`, and `assertions` JSON fields. Add a badge for the HTTP method.

- [ ] **Step 4: TestSuiteDetail view**
Build `TestSuiteDetail.tsx` that polls the test suite status (`pending` -> `generating` -> `ready`). Once ready, fetch and map the tests into `TestCard` components.

- [ ] **Step 5: Verify Full Flow**
1. Run backend and frontend. Set OPENAI_API_KEY in backend `.env`.
2. Select endpoints in frontend and click Generate.
3. Wait 10-15 seconds.
4. See test cards populate in the UI.

- [ ] **Step 6: Commit**
```bash
git add frontend/
git commit -m "feat(frontend): add test suite generation UI and JSON test viewer"
```

---

## Verification Checklist (end of Week 3)

- [ ] `litellm` handles API key integration successfully.
- [ ] Database correctly saves TestSuite and Test models.
- [ ] Endpoint Explorer allows test suite generation.
- [ ] Background task correctly creates structured outputs based on the OpenAPI endpoint context.
- [ ] UI properly displays JSON viewer cards for generated tests.
- [ ] `pytest -v` — all green
- [ ] `npm run build` succeeds in `frontend/`

When all 7 boxes are ticked, you are done with Week 3.

---

## Notes for Week 4

In Week 4, we will implement the actual HTTP runner using `httpx` to execute the tests we just generated against a live target API, and evaluate the results using `jsonpath-ng`. Failed tests will be analyzed by the LLM.
