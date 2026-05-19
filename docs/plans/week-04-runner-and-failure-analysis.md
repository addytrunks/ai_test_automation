# Week 4 Implementation Plan — Runner & Failure Analysis

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the generated test cases against a live target API using `httpx`. Evaluate assertions (using `jsonpath-ng`). For any failed test, pass the request/response details back to the LLM to generate an explanation and fix.

**Architecture:** We add the `runs`, `test_results`, and `ai_analyses` tables. The `runner` module handles async HTTP requests and assertion evaluation. The `analyzer` module handles sending failure data to LiteLLM. A background task runs the tests and performs the analysis. The UI gains a Run Detail view with test status indicators and a panel for AI analysis of failures.

**Tech Stack Additions:** `jsonpath-ng` for parsing JSON response bodies during assertions. 

**Verification gate:** Click "Run" on a test suite in the UI. See the run progress. Once finished, click on a test that failed against VAmPI. An AI-written explanation indicating why it failed (e.g., "Received 401 Unauthorized instead of 200 OK") will be visible.

---

## File Structure for Week 4

**Backend (`backend/`):**
- Modify: `app/models.py` — add Run, TestResult, AIAnalysis
- Add migration: `alembic/versions/..._add_runner_models.py`
- Create: `app/runner/__init__.py`, `app/runner/router.py`, `app/runner/service.py`, `app/runner/executor.py`, `app/runner/assertions.py`
- Create: `app/analyzer/__init__.py`, `app/analyzer/router.py`, `app/analyzer/failure_analysis.py`, `app/analyzer/schemas.py`, `app/analyzer/prompts.py`
- Modify: `app/main.py` — include `runner.router`, `analyzer.router`
- Create: `tests/test_runner.py`, `tests/test_analyzer.py`

**Frontend (`frontend/`):**
- Modify: `src/api/types.ts`
- Create: `src/api/runner.ts`
- Create: `src/pages/RunDetail.tsx` — Shows run summary and lists test results
- Create: `src/components/AssertionList.tsx` — Displays passed/failed assertions
- Create: `src/components/AIAnalysisPanel.tsx` — Displays LLM failure explanation
- Modify: `src/App.tsx` — Add run details route

---

## Task 1: Runner Dependencies

**Files:**
- Modify: `C:\AI_TEST_AUTOMATION\backend\pyproject.toml`

- [ ] **Step 1: Add dependencies**
Add `jsonpath-ng>=1.8.0` to dependencies.

- [ ] **Step 2: Install**
```bash
cd backend
pip install -e ".[dev]"
```

- [ ] **Step 3: Commit**
```bash
git add backend/pyproject.toml
git commit -m "chore(backend): add jsonpath-ng for assertions"
```

---

## Task 2: Database Models & Migration

**Files:**
- Modify: `C:\AI_TEST_AUTOMATION\backend\app\models.py`

- [ ] **Step 1: Add models**
In `app/models.py`:
```python
class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        primary_key=True,
        default=uuid.uuid4,
    )
    test_suite_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_suites.id", ondelete="CASCADE"), index=True)
    target_base_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True) # {total, passed, failed, errors}
    parent_run_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"), ForeignKey("runs.id"), nullable=True)
    loop_iteration: Mapped[int] = mapped_column(Integer, default=0)
    
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class TestResult(Base):
    __tablename__ = "test_results"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        primary_key=True,
        default=uuid.uuid4,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"), index=True)
    
    status: Mapped[str] = mapped_column(String(50), nullable=False) # passed/failed/error/skipped
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_headers: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    response_body: Mapped[dict[str, Any] | str | None] = mapped_column(JSONB, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    assertion_results: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
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
    test_result_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_results.id", ondelete="CASCADE"), unique=True, index=True)
    explanation: Mapped[str] = mapped_column(String, nullable=False)
    likely_cause: Mapped[str] = mapped_column(String, nullable=False)
    suggested_fix: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 2: Generate Alembic migration**
```bash
cd backend
alembic revision --autogenerate -m "add run and analysis models"
alembic upgrade head
```

- [ ] **Step 3: Commit**
```bash
git add backend/app/models.py backend/alembic/versions/
git commit -m "feat(db): add Run, TestResult, and AIAnalysis models"
```

---

## Task 3: Assertion Evaluation Module

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\backend\app\runner\assertions.py`
- Create: `C:\AI_TEST_AUTOMATION\backend\tests\test_assertions.py`

- [ ] **Step 1: Write Assertion Engine**

Write `app/runner/assertions.py` to handle the different assertion types from W1 specs (`status_eq`, `json_path`, `body_contains`, `header_eq`, `response_time_lt`).

```python
from jsonpath_ng import parse

def evaluate_assertions(assertions: list[dict], response_status: int, response_headers: dict, response_body: dict | str, duration_ms: int) -> tuple[bool, list[dict]]:
    results = []
    all_passed = True
    
    for assertion in assertions:
        type_ = assertion.get("type")
        passed = False
        actual = None
        error = None
        
        try:
            if type_ == "status_eq":
                expected = assertion.get("expected")
                actual = response_status
                passed = actual == expected
                
            elif type_ == "json_path":
                if not isinstance(response_body, dict):
                    error = "Response body is not JSON"
                else:
                    target = assertion.get("target")
                    op = assertion.get("op")
                    expected = assertion.get("expected")
                    
                    jsonpath_expr = parse(target)
                    matches = jsonpath_expr.find(response_body)
                    
                    if op == "exists":
                        passed = len(matches) > 0
                        actual = "exists" if passed else "not found"
                    elif op == "eq":
                        actual = matches[0].value if matches else None
                        passed = actual == expected
                        
            elif type_ == "body_contains":
                expected = assertion.get("expected")
                actual_str = str(response_body)
                passed = str(expected) in actual_str
                actual = "contained" if passed else "not contained"
                
            elif type_ == "header_eq":
                target = assertion.get("target", "").lower()
                expected = assertion.get("expected")
                # headers dict should have lowercase keys
                actual = response_headers.get(target)
                passed = actual == expected
                
            elif type_ == "response_time_lt":
                expected = assertion.get("expected")
                actual = duration_ms
                passed = actual < expected
        except Exception as e:
            error = str(e)
            
        if not passed:
            all_passed = False
            
        results.append({
            "assertion": assertion,
            "passed": passed,
            "actual": actual,
            "error": error
        })
        
    return all_passed, results
```

- [ ] **Step 2: Commit**
```bash
git add backend/app/runner/assertions.py
git commit -m "feat(runner): add jsonpath assertion evaluation engine"
```

---

## Task 4: HTTP Executor

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\backend\app\runner\executor.py`

- [ ] **Step 1: Write Executor**

Using `httpx.AsyncClient()`, iterate over tests. Interpolate `path_params` into the URL path. Execute the request, capture duration, status, body, headers. Call the assertion evaluator. Write `TestResult` to DB.

```python
import time
import uuid
import httpx
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Run, Test, TestResult
from app.runner.assertions import evaluate_assertions

async def execute_run(db: AsyncSession, run_id: uuid.UUID, tests: list[Test], base_url: str):
    run = await db.get(Run, run_id)
    run.status = "running"
    run.started_at = datetime.now(timezone.utc)
    await db.commit()
    
    summary = {"total": len(tests), "passed": 0, "failed": 0, "errors": 0}
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for test in tests:
            # Prepare path
            path = test.path
            if test.path_params:
                for k, v in test.path_params.items():
                    path = path.replace(f"{{{k}}}", str(v))
            
            url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
            start_time = time.time()
            error_message = None
            response_status = None
            response_headers = None
            response_body = None
            duration_ms = None
            all_passed = False
            assertion_results = []
            status = "error"
            
            try:
                response = await client.request(
                    method=test.method.upper(),
                    url=url,
                    params=test.query_params,
                    headers=test.headers,
                    json=test.body
                )
                duration_ms = int((time.time() - start_time) * 1000)
                response_status = response.status_code
                response_headers = dict(response.headers)
                try:
                    response_body = response.json()
                except:
                    response_body = {"raw": response.text}
                    
                all_passed, assertion_results = evaluate_assertions(
                    test.assertions or [], response_status, response_headers, response_body, duration_ms
                )
                status = "passed" if all_passed else "failed"
            except Exception as e:
                error_message = str(e)
                duration_ms = int((time.time() - start_time) * 1000)
                
            if status == "passed": summary["passed"] += 1
            elif status == "failed": summary["failed"] += 1
            else: summary["errors"] += 1
                
            tr = TestResult(
                run_id=run.id,
                test_id=test.id,
                status=status,
                response_status=response_status,
                response_headers=response_headers,
                response_body=response_body,
                duration_ms=duration_ms,
                assertion_results=assertion_results,
                error_message=error_message
            )
            db.add(tr)
            
    run.status = "completed"
    run.completed_at = datetime.now(timezone.utc)
    run.summary = summary
    await db.commit()
```

- [ ] **Step 2: Commit**
```bash
git add backend/app/runner/executor.py
git commit -m "feat(runner): add httpx test execution logic"
```

---

## Task 5: Failure Analysis (Analyzer)

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\backend\app\analyzer\schemas.py`
- Create: `C:\AI_TEST_AUTOMATION\backend\app\analyzer\failure_analysis.py`

- [ ] **Step 1: Write schemas**
In `analyzer/schemas.py`:
```python
from pydantic import BaseModel

class FailureExplanation(BaseModel):
    explanation: str
    likely_cause: str
    suggested_fix: str
```

- [ ] **Step 2: Write failure analysis logic**
In `analyzer/failure_analysis.py`, load failed test results, build a prompt with the expected assertions and the actual response, and call `generate_structured` from `app.llm.client`. Store the result in the `AIAnalysis` table.

```python
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import TestResult, Test, AIAnalysis
from app.llm.client import generate_structured
from app.analyzer.schemas import FailureExplanation
from app.analyzer.prompts import build_failure_prompt

async def analyze_failure(db: AsyncSession, test_result_id: uuid.UUID):
    # Fetch result and test
    tr = await db.get(TestResult, test_result_id)
    if not tr or tr.status != "failed": return
    
    test = await db.get(Test, tr.test_id)
    
    prompt = f"""
Analyze this API test failure.
Test Scenario: {test.name} ({test.scenario_type})
Request: {test.method} {test.path}
Assertions: {test.assertions}

Actual Response:
Status: {tr.response_status}
Body: {tr.response_body}

Assertion Results: {tr.assertion_results}
"""
    try:
        analysis_result = await generate_structured(prompt, FailureExplanation)
        
        analysis = AIAnalysis(
            test_result_id=tr.id,
            explanation=analysis_result.explanation,
            likely_cause=analysis_result.likely_cause,
            suggested_fix=analysis_result.suggested_fix
        )
        db.add(analysis)
        await db.commit()
    except Exception as e:
        # log failure silently
        pass
```

- [ ] **Step 3: Commit**
```bash
git add backend/app/analyzer/
git commit -m "feat(analyzer): add LLM failure explanation logic"
```

---

## Task 6: Runner & Analyzer Services/Routers

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\backend\app\runner\router.py`
- Modify: `C:\AI_TEST_AUTOMATION\backend\app\main.py`

- [ ] **Step 1: Background wrapper**
In `app/runner/service.py`, create a background task that calls `execute_run`, then fetches all failed `TestResult`s and calls `analyze_failure` on them.

- [ ] **Step 2: Runner Router**
Create `/test-suites/{suite_id}/runs` (POST to trigger, GET to list). Add endpoints to get `TestResult` lists and `AIAnalysis` for a specific result.

- [ ] **Step 3: Analyzer Router and Prompts**
Create `app/analyzer/prompts.py` to hold the prompt building logic for `build_failure_prompt`.
Create `app/analyzer/router.py` for `/test-suites/{suite_id}/coverage-analyze` to trigger on-demand coverage analysis (a placeholder returning an empty list for now until Week 5 fully implements it).

- [ ] **Step 4: Wire routers**
Include runner and analyzer routers in `app/main.py`.

- [ ] **Step 5: Runner initialization**
Create `app/runner/__init__.py`.

- [ ] **Step 6: Write Tests**
Write `tests/test_assertions.py` to verify all 5 jsonpath-ng assertion types.

- [ ] **Step 7: Commit**
```bash
git add backend/app/runner/ backend/app/analyzer/ backend/app/main.py backend/tests/
git commit -m "feat(runner): add API endpoints, background task integration, and analyzer logic"
```

---

## Task 7: Frontend UI

**Files:**
- Modify: `C:\AI_TEST_AUTOMATION\frontend\src\pages\TestSuiteDetail.tsx`
- Create: `C:\AI_TEST_AUTOMATION\frontend\src\pages\RunDetail.tsx`
- Create: `C:\AI_TEST_AUTOMATION\frontend\src\components\AssertionList.tsx`
- Create: `C:\AI_TEST_AUTOMATION\frontend\src\components\AIAnalysisPanel.tsx`

- [ ] **Step 1: Run detail view**
Build `RunDetail.tsx`. Show progress of the run. When complete, list the test results. Green check for pass, red X for fail. 

- [ ] **Step 2: AI Analysis Panel**
When a user clicks a failed test result, expand it to show the request/response payload, the `AssertionList`, and the `AIAnalysisPanel` displaying the explanation and suggested fix.

- [ ] **Step 3: Verify Full Flow**
1. Ensure VAmPI is running via docker-compose.
2. In the UI, set target URL to `http://localhost:5001`.
3. Trigger a run on the tests generated in Week 3.
4. Wait for it to complete. See passes and failures.
5. Expand a failed test and read the AI analysis.

- [ ] **Step 4: Commit**
```bash
git add frontend/
git commit -m "feat(frontend): add run details and AI analysis views"
```

---

## Verification Checklist (end of Week 4)

- [ ] httpx executor correctly interpolates path parameters and fires requests.
- [ ] jsonpath assertion engine evaluates the 5 assertion types correctly.
- [ ] Background task runs tests and immediately analyzes failures via LLM.
- [ ] UI shows test execution progress and final results.
- [ ] Failed tests in UI display LLM-written explanations and suggested fixes.
- [ ] `pytest -v` — all green
- [ ] `npm run build` succeeds in `frontend/`

When all 7 boxes are ticked, you are done with Week 4.

---

## Notes for Week 5

In Week 5, we will implement the full agentic loop using LangGraph, wrapping the runner and analyzer, and introducing a generator node to form a self-healing and self-improving test loop.
