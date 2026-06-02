# Week 5 Implementation Plan — Agentic Loop

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the closed agentic loop using LangGraph. The system will automatically analyze coverage gaps after a run, generate new tests for high-severity gaps, and re-run them without user intervention, bounded by strict safety caps.

**Architecture:** We add the `coverage_gaps` table. The `agentic` module defines a `StateGraph` with nodes: `execute_run_node`, `analyze_node`, and `generate_node`. A conditional edge checks `current_depth` against `max_depth` to prevent runaway loops. We use `langgraph-checkpoint-postgres` for durable state. The frontend gets a visualization of the run lineage.

**Tech Stack Additions:** `langgraph`, `langgraph-checkpoint-postgres`. React component `@xyflow/react` (formerly `react-flow`) for lineage visualization.

**Verification gate:** **Click Run → loop auto-runs 2-3 iterations → lineage tree shows new tests discovered without user clicks.** You should see tests automatically generated and executed to hit deeper gaps (like BOLA/IDOR issues in VAmPI).

---

## File Structure for Week 5

**Backend (`backend/`):**
- Modify: `app/models.py` — add CoverageGap
- Add migration: `alembic/versions/..._add_coverage_gaps.py`
- Create: `app/agentic/__init__.py`, `app/agentic/state.py`, `app/agentic/nodes.py`, `app/agentic/guards.py`, `app/agentic/graph.py`, `app/agentic/checkpointer.py`
- Modify: `app/analyzer/coverage_analysis.py` — Extract coverage analysis logic
- Modify: `app/runner/router.py` — Trigger LangGraph loop instead of bare execution
- Create: `tests/test_agentic.py`

**Frontend (`frontend/`):**
- Modify: `package.json` — add `reactflow`
- Create: `src/components/RunLineageTree.tsx` — Visualizer for run loops
- Create: `src/components/CoverageGapList.tsx` — Shows identified gaps
- Modify: `src/pages/RunDetail.tsx` — Integrate lineage and coverage gaps
- Modify: `src/pages/TestSuiteDetail.tsx`

---

## Task 1: LangGraph Dependencies

**Files:**
- Modify: `C:\AI_TEST_AUTOMATION\backend\pyproject.toml`
- Modify: `C:\AI_TEST_AUTOMATION\frontend\package.json`

- [ ] **Step 1: Backend Dependencies**
Add to `pyproject.toml`:
```toml
    "langgraph>=1.2.0",
    "langgraph-checkpoint-postgres>=3.0.5",
```

- [ ] **Step 2: Frontend Dependencies**
```bash
cd frontend
npm install @xyflow/react
```

- [ ] **Step 3: Install**
```bash
cd backend
uv pip install -e ".[dev]"
```

- [ ] **Step 4: Commit**
```bash
git add backend/pyproject.toml frontend/package.json
git commit -m "chore: add langgraph and reactflow deps"
```

---

## Task 2: Database Models & Migration

**Files:**
- Modify: `C:\AI_TEST_AUTOMATION\backend\app\models.py`

- [ ] **Step 1: Add CoverageGap model**
In `app/models.py`:
```python
class CoverageGap(Base):
    __tablename__ = "coverage_gaps"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        primary_key=True,
        default=uuid.uuid4,
    )
    test_suite_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_suites.id", ondelete="CASCADE"), index=True)
    endpoint_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("endpoints.id", ondelete="CASCADE"), index=True)
    
    scenario_description: Mapped[str] = mapped_column(String(1024), nullable=False)
    severity: Mapped[str] = mapped_column(String(50), nullable=False) # low/medium/high
    
    # run_id links this gap to the specific iteration that surfaced it.
    # Without this, the lineage tree cannot attribute which gaps came from which run.
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        ForeignKey("runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    spawned_test_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"), ForeignKey("tests.id"), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 2: Generate Alembic migration**
```bash
cd backend
alembic revision --autogenerate -m "add coverage gaps"
alembic upgrade head
```

- [ ] **Step 3: Commit**
```bash
git add backend/app/models.py backend/alembic/versions/
git commit -m "feat(db): add CoverageGap model"
```

---

## Task 3: Coverage Analysis Logic

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\backend\app\analyzer\coverage_analysis.py`

- [ ] **Step 1: Write Coverage Analyzer**
Analyze existing tests and their run results for a suite to find unhandled paths, parameter injections, or security gaps (e.g., IDOR/BOLA, unauthenticated access). The function must receive a `run_id` so it can pass actual test outcomes to the LLM — without this, the LLM is guessing about coverage rather than reasoning from evidence.

```python
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models import TestSuite, Endpoint, Test, TestResult, CoverageGap
from app.llm.client import generate_structured
from pydantic import BaseModel

class GapSchema(BaseModel):
    endpoint_path: str
    scenario_description: str
    severity: str  # low/medium/high

class GapListSchema(BaseModel):
    gaps: list[GapSchema]

async def analyze_coverage_gaps(
    db: AsyncSession, suite_id: uuid.UUID, run_id: uuid.UUID
) -> list[CoverageGap]:
    """Analyze coverage gaps using actual test definitions and run results.
    
    Args:
        db: Database session.
        suite_id: The test suite to analyze.
        run_id: The specific run whose results inform the gap analysis.
    """
    suite = await db.get(TestSuite, suite_id)
    if not suite:
        return []

    # (a) Fetch all endpoints for this spec
    ep_result = await db.execute(
        select(Endpoint).where(Endpoint.spec_id == suite.spec_id)
    )
    endpoints_list = ep_result.scalars().all()
    endpoints_by_id = {ep.id: ep for ep in endpoints_list}

    # (b) Fetch all Test records for the suite, grouped by endpoint
    test_result = await db.execute(
        select(Test).where(Test.test_suite_id == suite_id)
    )
    tests = test_result.scalars().all()
    tests_by_endpoint: dict[uuid.UUID, list[Test]] = {}
    for t in tests:
        tests_by_endpoint.setdefault(t.endpoint_id, []).append(t)

    # (c) Fetch all TestResult records for the given run_id
    tr_result = await db.execute(
        select(TestResult).where(TestResult.run_id == run_id)
    )
    test_results = tr_result.scalars().all()
    results_by_test_id = {tr.test_id: tr for tr in test_results}

    # Build a structured summary for the LLM
    endpoint_summaries = []
    for ep in endpoints_list:
        ep_tests = tests_by_endpoint.get(ep.id, [])
        test_details = []
        for t in ep_tests:
            tr = results_by_test_id.get(t.id)
            test_details.append({
                "name": t.name,
                "description": t.description,
                "scenario_type": t.scenario_type,
                "status": tr.status if tr else "not_run",
                "assertion_results": tr.assertion_results if tr else None,
            })
        endpoint_summaries.append({
            "method": ep.method,
            "path": ep.path,
            "summary": ep.summary,
            "test_count": len(ep_tests),
            "tests": test_details,
        })

    prompt = f"""Analyze the test coverage for this API suite based on ACTUAL test results.

Endpoints and their test outcomes:
{endpoint_summaries}

For each endpoint, consider:
1. Are there endpoints with ZERO tests? (high severity)
2. Which tests FAILED — do the failures indicate missing negative/security tests?
3. Are there untested scenario types (auth_bypass, BOLA/IDOR, boundary, injection)?
4. Are there parameter combinations or edge cases not covered?

Return only HIGH and MEDIUM severity gaps. Prioritize BOLA/IDOR and auth_bypass."""

    try:
        result = await generate_structured(prompt, GapListSchema)

        gaps = []
        for g in result.gaps:
            matched_ep = next(
                (ep for ep in endpoints_list if ep.path == g.endpoint_path),
                None,
            )
            if not matched_ep:
                continue

            gap = CoverageGap(
                test_suite_id=suite_id,
                endpoint_id=matched_ep.id,
                scenario_description=g.scenario_description,
                severity=g.severity,
            )
            db.add(gap)
            gaps.append(gap)

        await db.commit()
        return gaps
    except Exception:
        return []
```

- [ ] **Step 2: Commit**
```bash
git add backend/app/analyzer/
git commit -m "feat(analyzer): add coverage gap analysis with run-result awareness"
```

---

## Task 4: Agentic Loop State and Checkpointer

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\backend\app\agentic\state.py`
- Create: `C:\AI_TEST_AUTOMATION\backend\app\agentic\checkpointer.py`
- Modify: `C:\AI_TEST_AUTOMATION\backend\app\config.py`
- Modify: `C:\AI_TEST_AUTOMATION\.env.example`

- [ ] **Step 1: Define State**
In `app/agentic/state.py`:
```python
from typing import TypedDict, Literal
import uuid

class AgenticLoopState(TypedDict):
    test_suite_id: str
    target_base_url: str
    current_depth: int
    max_depth: int
    max_tests_per_cycle: int
    last_run_id: str | None
    last_gaps: list[dict]
    new_test_ids: list[str]
    total_tokens_used: int
    final_status: Literal["completed", "max_depth_hit", "no_high_gaps", "error"] | None
```

- [ ] **Step 2: Add `CHECKPOINTER_URL` to config**
Do **not** derive the psycopg3 conninfo from `DATABASE_URL` via string replacement. `DATABASE_URL` uses the `postgresql+asyncpg://` scheme for SQLAlchemy; psycopg3 requires a plain `postgresql://` scheme. These are fundamentally different drivers with different connection semantics.

In `.env.example`, add:
```dotenv
# DATABASE_URL is for SQLAlchemy + asyncpg (the app ORM).
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/api_test_platform

# CHECKPOINTER_URL is for langgraph-checkpoint-postgres (psycopg3).
# This MUST be a psycopg3-compatible URL (postgresql:// scheme, NOT asyncpg).
# It typically points to the same database but uses a different driver.
CHECKPOINTER_URL=postgresql://user:pass@localhost:5432/api_test_platform
```

In `app/config.py`, add:
```python
checkpointer_url: str = Field(
    ...,
    description="psycopg3-compatible connection string for LangGraph checkpointer. "
    "Must use postgresql:// scheme, NOT postgresql+asyncpg://.",
)
```

- [ ] **Step 3: Checkpointer integration**
In `app/agentic/checkpointer.py`, use the modern `from_conn_string` context manager. This is the pattern documented by LangGraph and avoids manually managing `psycopg_pool` lifecycle. Note: the checkpointer must be passed to `build_graph()` at compile time — see Task 5 Step 4.
```python
from contextlib import asynccontextmanager
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.config import get_settings

@asynccontextmanager
async def get_checkpointer():
    settings = get_settings()
    async with AsyncPostgresSaver.from_conn_string(settings.checkpointer_url) as saver:
        await saver.setup()  # Creates checkpoint tables on first use; idempotent after that
        yield saver
```

- [ ] **Step 4: Guards (optional — `decide_continue` already covers this)**
`guards.py` was originally planned to enforce safety limits by raising exceptions. **Do not call this from inside nodes.** Raising inside a node causes the graph to fail rather than route gracefully to `finalize`. The `decide_continue` routing function already handles `max_depth` and token budget checks and routes to `finalize` cleanly.

Create `app/agentic/guards.py` only if you want a standalone utility for pre-flight validation *before* invoking the graph (e.g., rejecting a run request with bad config from the router). If created, it must **not** be called from within graph nodes.

```python
# app/agentic/guards.py — PRE-FLIGHT VALIDATION ONLY, NOT for use inside nodes
from app.agentic.state import AgenticLoopState

def validate_initial_state(state: AgenticLoopState):
    """Validate starting state before graph.ainvoke(). Raises ValueError for bad config."""
    if state["max_depth"] < 1 or state["max_depth"] > 5:
        raise ValueError(f"max_depth must be 1–5, got {state['max_depth']}")
    if state["max_tests_per_cycle"] < 1 or state["max_tests_per_cycle"] > 10:
        raise ValueError(f"max_tests_per_cycle must be 1–10, got {state['max_tests_per_cycle']}")
```

- [ ] **Step 5: Commit**
```bash
git add backend/app/agentic/ backend/app/config.py .env.example
git commit -m "feat(agentic): add LangGraph state, checkpointer with dedicated CHECKPOINTER_URL"
```

---

## Task 5: Agentic Nodes & Graph

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\backend\app\agentic\nodes.py`
- Create: `C:\AI_TEST_AUTOMATION\backend\app\agentic\graph.py`
- Modify: `C:\AI_TEST_AUTOMATION\backend\app\models.py` — add `generation_hash` column to `Test`
- Add migration: `alembic/versions/..._add_generation_hash.py`

- [ ] **Step 1: Add `generation_hash` column to Test model**
In `app/models.py`, add to the `Test` model:
```python
generation_hash: Mapped[str | None] = mapped_column(
    String(64), nullable=True, index=True,
    comment="SHA-256 of endpoint_id:scenario_type:normalized_description for dedup",
)

__table_args__ = (
    UniqueConstraint("test_suite_id", "generation_hash", name="uq_test_suite_generation_hash"),
)
```
Generate and run the Alembic migration:
```bash
cd backend
alembic revision --autogenerate -m "add generation_hash to tests"
alembic upgrade head
```

- [ ] **Step 2: Implement Nodes**
In `app/agentic/nodes.py`, write:
1. `execute_run_node`: Uses `app.runner.executor` to run tests. Updates `last_run_id`. Returns `{"last_run_id": ..., "current_depth": state["current_depth"] + 1}`.
2. `analyze_node`: Performs **two distinct LLM calls**: loops over failed tests to generate `AIAnalysis` (failure analysis), then calls `app.analyzer.coverage_analysis.analyze_coverage_gaps(db, suite_id, run_id)` — passing `last_run_id` from state — to find gaps. Stores serialized gaps in `last_gaps`. Returns `{"last_gaps": ...}`.
3. `generate_node`: Reads `last_gaps`, enforces `max_tests_per_cycle <= 10`, generates new tests. **Before persisting any new Test**, implements explicit deduplication:

```python
import hashlib
from sqlalchemy import select
from app.models import Test

def compute_generation_hash(endpoint_id: str, scenario_type: str, description: str) -> str:
    """Compute SHA-256 dedup hash.
    
    NOTE: This is string-based deduplication. Two semantically identical
    descriptions with different wording (e.g., 'Test BOLA on /users/{id}' vs
    'Test BOLA on /users/{user_id}') will produce different hashes.
    Acceptable for a POC; a production system would need semantic similarity.
    """
    raw = f"{endpoint_id}:{scenario_type}:{description.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()

# Inside generate_node:
async def generate_node(state: AgenticLoopState) -> dict:
    # ... (generate tests from gaps via LLM) ...
    
    # Fetch existing hashes for this suite to skip duplicates
    existing_hashes_result = await db.execute(
        select(Test.generation_hash).where(
            Test.test_suite_id == suite_id,
            Test.generation_hash.isnot(None),
        )
    )
    existing_hashes = set(existing_hashes_result.scalars().all())
    
    new_test_ids = []
    for generated_test in generated_tests:
        gen_hash = compute_generation_hash(
            str(generated_test.endpoint_id),
            generated_test.scenario_type,
            generated_test.description,
        )
        
        # Skip if this exact test was already generated
        if gen_hash in existing_hashes:
            continue
        
        test = Test(
            test_suite_id=suite_id,
            endpoint_id=generated_test.endpoint_id,
            # ... other fields ...
            auto_generated=True,
            parent_coverage_gap_id=generated_test.gap_id,
            generation_depth=state["current_depth"],
            generation_hash=gen_hash,
        )
        db.add(test)
        existing_hashes.add(gen_hash)  # prevent intra-batch duplicates
        new_test_ids.append(str(test.id))
    
    await db.commit()
    return {"new_test_ids": new_test_ids}
```
The `UniqueConstraint` on `(test_suite_id, generation_hash)` acts as a DB-level safeguard against race conditions.

- [ ] **Step 3: Implement routing (pure function) and finalize_node**
`decide_continue` is a LangGraph conditional-edge routing function. It **must be pure** — it returns a routing key string and must **not** mutate state. All `state["final_status"] = ...` assignments are removed.

Terminal status is instead set by a `finalize_node` that the graph routes to before `END`.

```python
# --- Pure routing function (no state mutation) ---
def decide_continue(state: AgenticLoopState) -> Literal["continue", "finalize"]:
    """Pure routing function. Returns a routing key only. Does NOT mutate state."""
    if state["current_depth"] >= min(state["max_depth"], 5):
        return "finalize"
    if state["total_tokens_used"] >= 200000:
        return "finalize"
    high = [g for g in state["last_gaps"] if g.get("severity") == "high"]
    if not high:
        return "finalize"
    return "continue"

# --- Terminal node that sets final_status ---
def finalize_node(state: AgenticLoopState) -> dict:
    """Determine and return the terminal status based on current state."""
    if state["current_depth"] >= min(state["max_depth"], 5):
        return {"final_status": "max_depth_hit"}
    if state["total_tokens_used"] >= 200000:
        return {"final_status": "error"}
    high = [g for g in state["last_gaps"] if g.get("severity") == "high"]
    if not high:
        return {"final_status": "no_high_gaps"}
    return {"final_status": "completed"}
```

- [ ] **Step 4: Build Graph**
In `app/agentic/graph.py`:
```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.base import BaseCheckpointSaver
from app.agentic.state import AgenticLoopState
from app.agentic.nodes import (
    execute_run_node, analyze_node, generate_node,
    decide_continue, finalize_node,
)

def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    """
    Build and compile the agentic loop graph.

    IMPORTANT: The checkpointer MUST be passed here at compile time.
    It cannot be injected later at ainvoke() time. If no checkpointer
    is provided (e.g., in unit tests), the graph runs without persistence.
    """
    workflow = StateGraph(AgenticLoopState)

    workflow.add_node("execute_run", execute_run_node)
    workflow.add_node("analyze", analyze_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("finalize", finalize_node)

    # Use add_edge(START, ...) — set_entry_point() is deprecated in LangGraph 1.x
    workflow.add_edge(START, "execute_run")
    workflow.add_edge("execute_run", "analyze")

    workflow.add_conditional_edges(
        "analyze",
        decide_continue,
        {
            "continue": "generate",
            "finalize": "finalize",
        },
    )

    workflow.add_edge("generate", "execute_run")
    workflow.add_edge("finalize", END)

    return workflow.compile(checkpointer=checkpointer)
```

- [ ] **Step 5: Commit**
```bash
git add backend/app/agentic/ backend/app/models.py backend/alembic/versions/
git commit -m "feat(agentic): implement LangGraph nodes with pure routing, dedup, and finalize_node"
```

- [ ] **Step 6: Throwaway Graph Test**
Create `tests/throwaway_graph.py` as a 2-node graph to internalize the LangGraph API before wiring to router. Run it locally.

---

## Task 6: Hook loop into API

**Files:**
- Modify: `C:\AI_TEST_AUTOMATION\backend\app\runner\router.py`

- [ ] **Step 1: Start Graph from Router**
Change the `POST /runs` endpoint to initialize the `AgenticLoopState` and run the graph in a background task.

Two wiring requirements that the naive version misses:

**A) Checkpointer must be passed at compile time, not invoked around ainvoke:**
```python
# router.py
from app.agentic.checkpointer import get_checkpointer
from app.agentic.graph import build_graph
from app.agentic.state import AgenticLoopState

@router.post("/runs")
async def create_run(payload: RunCreate, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    # ... create Run record, etc. ...
    background_tasks.add_task(run_agentic_loop, suite_id=payload.test_suite_id, run_id=new_run.id)
    return new_run

async def run_agentic_loop(suite_id: uuid.UUID, run_id: uuid.UUID):
    async with get_checkpointer() as checkpointer:
        graph = build_graph(checkpointer=checkpointer)  # compile with checkpointer
        
        initial_state: AgenticLoopState = {
            "test_suite_id": str(suite_id),
            "target_base_url": "http://localhost:5001",
            "current_depth": 0,
            "max_depth": 3,
            "max_tests_per_cycle": 10,
            "last_run_id": None,
            "last_gaps": [],
            "new_test_ids": [],
            "total_tokens_used": 0,
            "final_status": None,
        }
        
        # thread_id is REQUIRED for the checkpointer to key state correctly.
        # Without it, LangGraph raises a runtime error when checkpointing is enabled.
        config = {"configurable": {"thread_id": str(run_id)}}
        
        await graph.ainvoke(initial_state, config=config)
```

**B) DB session inside nodes:** Node functions run in a background task and cannot share the request-scoped `AsyncSession`. Each node that touches the DB must create its own session:
```python
# Inside a node:
from app.database import AsyncSessionLocal  # your sessionmaker

async def analyze_node(state: AgenticLoopState) -> dict:
    async with AsyncSessionLocal() as db:
        gaps = await analyze_coverage_gaps(db, uuid.UUID(state["test_suite_id"]), uuid.UUID(state["last_run_id"]))
    # ...
```

- [ ] **Step 2: Commit**
```bash
git add backend/app/runner/router.py
git commit -m "feat(runner): trigger LangGraph agentic loop on test suite run"
```

---

## Task 7: Frontend UI - Lineage Tree

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\frontend\src\components\RunLineageTree.tsx`
- Modify: `C:\AI_TEST_AUTOMATION\frontend\src\pages\RunDetail.tsx`

- [ ] **Step 1: Lineage Tree Component**
Use `reactflow` to draw a tree showing the user-triggered Run (depth 0) and the subsequent auto-generated runs (depth 1, depth 2). Clicking a node in the tree should show the summary for that specific run iteration.

- [ ] **Step 2: Coverage Gaps List**
Add a component to display the identified Coverage Gaps and their severity levels to the user.

- [ ] **Step 3: Verify Full Loop**
1. Run backend and frontend.
2. Select target VAmPI. Trigger a run on a suite.
3. Watch the UI (poll for updates). You should see the first run finish.
4. Then a new generating phase starts.
5. Then a second run occurs.
6. The lineage tree should display this progression.

- [ ] **Step 4: Prod Dry-run**
Verify `docker-compose.prod.yml` locally to ensure production deployment is ready.

- [ ] **Step 5: Commit**
```bash
git add frontend/
git commit -m "feat(frontend): add run lineage visualization and coverage gaps"
```

---

## Verification Checklist (end of Week 5)

- [ ] Coverage gaps are successfully identified by LLM and persisted (with `run_id` FK populated).
- [ ] LangGraph correctly orchestrates the execute -> analyze -> generate flow.
- [ ] Loop respects hard limits (max_depth <= 5).
- [ ] UI visualizes the multiple iterations visually via React Flow.
- [ ] New tests created by the loop correctly flag `auto_generated=true` and link to their `parent_coverage_gap_id`.
- [ ] `pytest -v` — all green
- [ ] `npm run build` succeeds in `frontend/`

**Known technical debt (acceptable for POC, document in Week 6 ADR):**
- `decide_continue` and `finalize_node` contain duplicated logic. Both must be kept in sync manually. In production, `finalize_node` would read the routing key returned by `decide_continue` from state rather than re-evaluating the same conditions.
- Hash-based deduplication is string-exact, not semantic. Two LLM-generated descriptions for the same test scenario with different wording produce different hashes and both get stored. Acceptable for Week 5; note it explicitly in the Week 6 ADR.

When all 7 boxes are ticked, you are done with Week 5.

---

## Notes for Weeks 6 and 7

Weeks 6 and 7 will focus on documentation, ADRs, and no code commits. We will justify the architectural decisions made in Weeks 1-5.