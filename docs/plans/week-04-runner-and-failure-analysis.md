# Week 4 Implementation Plan — Runner & Failure Analysis

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
    summary: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True
    )  # {total, passed, failed, errors}
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

Write `app/runner/assertions.py` to handle ALL 7 assertion types from the generator schema (`status_eq`, `status_in`, `json_path`, `body_contains`, `body_not_contains`, `header_eq`, `response_time_lt`).

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

            elif type_ == "status_in":
                expected = assertion.get("expected")  # list of ints
                actual = response_status
                passed = actual in (expected or [])
                
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

            elif type_ == "body_not_contains":
                expected = assertion.get("expected")
                actual_str = str(response_body)
                passed = str(expected) not in actual_str
                actual = "not contained" if passed else "contained"
                
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

- [ ] **Step 1: Write `interpolate_payload` helper**

Recursive variable resolver. Walks dicts, lists, and strings. Leaves non-string scalars (int, bool, None) untouched.

```python
import re
from typing import Any

def interpolate_payload(obj: Any, context: dict[str, str]) -> Any:
    """Recursively resolve {{VAR}} placeholders in dicts, lists, and strings."""
    if isinstance(obj, str):
        return re.sub(r"\{\{(\w+)\}\}", lambda m: context.get(m.group(1), m.group(0)), obj)
    elif isinstance(obj, dict):
        return {k: interpolate_payload(v, context) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [interpolate_payload(item, context) for item in obj]
    return obj  # int, bool, float, None — pass through
```

- [ ] **Step 2: Write Two-Pass Executor**

Using `httpx.AsyncClient()`, execute tests in two passes:
- **Pass 1 (Setup):** Run `scenario_type: "setup"` tests first, sequentially. Extract response values via `jsonpath-ng` using each test's `extract` mapping. Merge `static_context` values. Populate a `runtime_context` dict.
- **Pass 2 (Execute):** Run remaining tests with all payloads resolved via `interpolate_payload()`.

Both passes write `TestResult` rows through the same path — setup tests are fully visible in the UI.

```python
import time
import uuid
import httpx
import logging
from datetime import datetime, timezone
from jsonpath_ng import parse as jp_parse
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Run, Test, TestResult
from app.runner.assertions import evaluate_assertions

logger = logging.getLogger(__name__)

async def _execute_single_test(
    client: httpx.AsyncClient,
    db: AsyncSession,
    run: Run,
    test: Test,
    base_url: str,
    runtime_context: dict[str, str],
) -> TestResult:
    """Execute one test, write TestResult, return it."""
    # Resolve template variables in all payloads
    path = interpolate_payload(test.path, runtime_context)
    headers = interpolate_payload(test.headers, runtime_context)
    body = interpolate_payload(test.body, runtime_context)
    query_params = interpolate_payload(test.query_params, runtime_context)
    
    # Interpolate path params
    path_params = interpolate_payload(test.path_params, runtime_context)
    if path_params:
        for k, v in path_params.items():
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
            params=query_params,
            headers=headers,
            json=body,
        )
        duration_ms = int((time.time() - start_time) * 1000)
        response_status = response.status_code
        response_headers = dict(response.headers)
        try:
            response_body = response.json()
        except Exception:
            response_body = {"raw": response.text}
            
        all_passed, assertion_results = evaluate_assertions(
            test.assertions or [], response_status, response_headers, response_body, duration_ms
        )
        status = "passed" if all_passed else "failed"
    except Exception as e:
        error_message = str(e)
        duration_ms = int((time.time() - start_time) * 1000)
        
    tr = TestResult(
        run_id=run.id,
        test_id=test.id,
        status=status,
        response_status=response_status,
        response_headers=response_headers,
        response_body=response_body,
        duration_ms=duration_ms,
        assertion_results=assertion_results,
        error_message=error_message,
    )
    db.add(tr)
    return tr


async def execute_run(db: AsyncSession, run_id: uuid.UUID, tests: list[Test], base_url: str):
    run = await db.get(Run, run_id)
    run.status = "running"
    run.started_at = datetime.now(timezone.utc)
    await db.commit()
    
    summary = {"total": len(tests), "passed": 0, "failed": 0, "errors": 0}
    runtime_context: dict[str, str] = {}
    
    # Split tests into setup and execution phases
    setup_tests = [t for t in tests if t.scenario_type == "setup"]
    exec_tests = [t for t in tests if t.scenario_type != "setup"]
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # ── Pass 1: Setup tests (sequential, populate runtime_context) ──
        for test in setup_tests:
            # Dedup: skip if all extract keys are already populated
            if test.extract and all(k in runtime_context for k in test.extract):
                logger.info("Skipping duplicate setup test '%s' — context already has %s", test.name, list(test.extract.keys()))
                summary["total"] -= 1  # don't count skipped setup in total
                continue

            tr = await _execute_single_test(client, db, run, test, base_url, runtime_context)
            
            # Extract values from response for runtime context
            if tr.status == "passed" and test.extract and isinstance(tr.response_body, dict):
                for var_name, jsonpath_expr in test.extract.items():
                    try:
                        matches = jp_parse(jsonpath_expr).find(tr.response_body)
                        if matches:
                            runtime_context[var_name] = str(matches[0].value)
                            logger.info("Setup extracted %s = %s...", var_name, str(matches[0].value)[:20])
                    except Exception as e:
                        logger.warning("Failed to extract %s: %s", var_name, e)
            
            # Merge static_context
            if test.static_context:
                runtime_context.update(test.static_context)
            
            if tr.status == "passed": summary["passed"] += 1
            elif tr.status == "failed": summary["failed"] += 1
            else: summary["errors"] += 1
        
        # ── Pass 2: Execute remaining tests with resolved context ──
        for test in exec_tests:
            tr = await _execute_single_test(client, db, run, test, base_url, runtime_context)
            
            if tr.status == "passed": summary["passed"] += 1
            elif tr.status == "failed": summary["failed"] += 1
            else: summary["errors"] += 1
            
    run.status = "analyzing"
    run.completed_at = datetime.now(timezone.utc)
    run.summary = summary
    await db.commit()
```

> **Note:** The run transitions through `pending → running → analyzing → completed`.
> After `analyzing` is set, the service layer calls `analyze_failure()` on each failed result (see Task 6).
> Each `AIAnalysis` row is committed individually so the frontend can poll and display them as they arrive.
> The service layer sets `run.status = "completed"` after all analyses finish.
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
In `analyzer/failure_analysis.py`, load failed test results, build a prompt with **three layers of context** (intent, expected, actual), and call `generate_structured` from `app.llm.client`. Store the result in the `AIAnalysis` table.

The prompt must include:
1. **Intent:** test name, description, and scenario_type (critical for BOLA/auth_bypass where the *kind* of failure matters)
2. **Expected:** the full assertion list (what was supposed to happen)
3. **Actual:** response status, headers, AND body (for BOLA, the leaked data in the response body is the most important part)

```python
import logging
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import TestResult, Test, AIAnalysis
from app.llm.client import generate_structured
from app.analyzer.schemas import FailureExplanation

logger = logging.getLogger(__name__)

async def analyze_failure(db: AsyncSession, test_result_id: uuid.UUID):
    # Fetch result and test
    tr = await db.get(TestResult, test_result_id)
    if not tr or tr.status != "failed": return
    
    test = await db.get(Test, tr.test_id)
    
    prompt = f"""
Analyze this API test failure.

== TEST INTENT ==
Name: {test.name}
Description: {test.description}
Scenario Type: {test.scenario_type}
Request: {test.method} {test.path}

== EXPECTED BEHAVIOR ==
Expected Status: {test.expected_status}
Assertions: {test.assertions}

== ACTUAL RESPONSE ==
Status Code: {tr.response_status}
Response Headers: {tr.response_headers}
Response Body: {_truncate_body(tr.response_body)}

== ASSERTION RESULTS ==
{tr.assertion_results}
"""
```

Add a helper to compact and truncate the response body (prevents token limit blowups on verbose APIs):
```python
import json

MAX_BODY_CHARS = 4000

def _truncate_body(body: dict | str | None) -> str:
    if body is None:
        return "<empty>"
    if isinstance(body, dict):
        s = json.dumps(body, separators=(',', ':'))
    else:
        s = str(body)
    if len(s) > MAX_BODY_CHARS:
        return s[:MAX_BODY_CHARS] + "\n[TRUNCATED]"
    return s
```
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
        logger.warning("Failed to analyze test result %s: %s", test_result_id, e)
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
In `app/runner/service.py`, create a background task that:
1. Calls `execute_run()` (which sets status to `analyzing` on completion)
2. Fetches all failed `TestResult`s for this run
3. Calls `analyze_failure()` on each, committing each `AIAnalysis` row individually so the frontend can poll and display them progressively
4. Sets `run.status = "completed"` after all analyses finish

- [ ] **Step 2: Runner Router**
Create `/test-suites/{suite_id}/runs` (POST to trigger, GET to list). Add endpoints to get `TestResult` lists and `AIAnalysis` for a specific result.

**Ownership verification is required on every endpoint.** Follow the existing pattern: `Run → TestSuite → Project → user_id == current_user.id`. For test-result-level endpoints: `TestResult → Run → TestSuite → Project → user_id`. Without this, any authenticated user can read any run by ID.

- [ ] **Step 3: Analyzer Router and Prompts**
Create `app/analyzer/prompts.py` to hold the prompt building logic for `build_failure_prompt`.
Create `app/analyzer/router.py` for `/test-suites/{suite_id}/coverage-analyze` to trigger on-demand coverage analysis (a placeholder returning an empty list for now until Week 5 fully implements it).

- [ ] **Step 4: Wire routers**
Include runner and analyzer routers in `app/main.py`.

- [ ] **Step 5: Runner initialization**
Create `app/runner/__init__.py`.

- [ ] **Step 6: Write Tests**
Write `tests/test_assertions.py` to verify all 7 assertion types.

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

- [ ] httpx executor correctly interpolates path parameters and template variables, fires requests.
- [ ] jsonpath assertion engine evaluates all 7 assertion types correctly.
- [ ] Setup tests run first, extract tokens, and deduplicate redundant setup calls.
- [ ] Background task runs tests → sets status to `analyzing` → analyzes failures → sets `completed`.
- [ ] All router endpoints verify ownership (Run/TestResult → TestSuite → Project → user_id).
- [ ] UI shows test execution progress and final results.
- [ ] Failed tests in UI display LLM-written explanations and suggested fixes (appear progressively).
- [ ] `pytest -v` — all green
- [ ] `npm run build` succeeds in `frontend/`

When all 9 boxes are ticked, you are done with Week 4.

---

## Notes for Week 5

In Week 5, we will implement the full agentic loop using LangGraph, wrapping the runner and analyzer, and introducing a generator node to form a self-healing and self-improving test loop.
