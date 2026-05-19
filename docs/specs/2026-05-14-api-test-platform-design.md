# AI-Assisted API Test Generation Platform — Design Specification

| | |
|---|---|
| **Status** | Approved 2026-05-14 — *living document* |
| **Type** | Internship POC, 8 weeks, "production-style" |
| **Difficulty** | High |
| **Repo root** | `C:\test_claude_code` (fresh start) |

## Change history

| Date | Change | Driver |
|---|---|---|
| 2026-05-14 | Initial design approved across all 5 brainstorming sections | Brainstorming with user |

> Significant pivots after this point should be logged as ADRs in `docs/adr/` rather than rewriting this document. The phase plan is a target, not a contract.

---

## 1. Executive Summary

A web platform where a user uploads an OpenAPI specification, the system **generates structured test cases** for selected endpoints using an LLM, **executes** them against a live target API, **analyzes failures** with AI, and — most distinctively — runs an **agentic loop** that observes results, identifies coverage gaps, autonomously generates new tests for high-severity gaps, and re-executes. The platform demonstrates real-world value by discovering genuine vulnerabilities in **VAmPI** (a deliberately vulnerable Flask API) during the demo.

### Three distinguishing characteristics

1. **Data-driven test execution.** Tests are stored as structured JSON (`method`, `path`, `headers`, `body`, `assertions`), not Python code. The runner uses `httpx` directly — no `pytest`, no subprocess, no on-disk test files, no arbitrary code execution.
2. **A closed agentic loop.** After every run, an analyzer identifies high-severity coverage gaps; a generator produces new tests; the loop re-executes them. Safety caps prevent runaway. The loop is orchestrated by **LangGraph** as an explicit state machine.
3. **Provider-agnostic LLM layer.** All LLM calls go through **LiteLLM**, allowing the system to switch between OpenAI, Anthropic, and local models via a single environment variable.

---

## 2. Goals & Non-Goals

### Goals

- Single-user-per-account multi-tenant platform with JWT auth.
- Upload OpenAPI 3.x specs; parse and surface endpoints.
- Generate functional and security-flavored test cases per endpoint via LLM (positive, negative, auth_bypass, BOLA, boundary, injection).
- Execute generated tests against a live HTTP target; record full request/response detail.
- AI-written explanation + suggested fix for every failed test.
- AI-identified coverage gaps with severity classification.
- Closed agentic loop: auto-analyze → auto-generate → auto-run until termination.
- LiteLLM-based provider abstraction.
- Live cloud deployment by Week 8.
- Recorded 5-minute demo + slide deck.

### Non-Goals (explicitly out of scope)

- Email verification, password reset, OAuth, MFA.
- Multi-user roles / team workspaces / RBAC.
- Test scheduling, CI/CD-native integration as a service (mentioned as future work only).
- Persistent test history beyond what fits a single user's view.
- Real production-grade observability (Sentry, Prometheus, tracing) — `structlog` JSON output is enough.
- Performance under load — scale target is "one user, ≤ 10 concurrent runs".
- Cross-spec features beyond OpenAPI 3.x (no GraphQL, gRPC, AsyncAPI).
- Mutation testing, contract testing, property-based testing beyond what LLM happens to produce.
- Mobile responsive frontend (desktop browser only).

---

## 3. Architecture Overview

### System diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                    React SPA  (Vite + TypeScript)                │
│  Login │ Dashboard │ Specs │ Endpoints │ Tests │ Runs │ Reports  │
└─────────────────────────────┬────────────────────────────────────┘
                              │  HTTPS + JWT (Bearer)
┌─────────────────────────────▼────────────────────────────────────┐
│                  FastAPI Monolith   (app.main)                   │
│                                                                  │
│  ┌─────────┬────────┬───────────┬─────────┬───────────────────┐  │
│  │  auth   │ specs  │ generator │ runner  │     analyzer      │  │
│  │  (JWT,  │(parse  │ (LLM +    │(httpx   │ (failure expl.    │  │
│  │  users) │OpenAPI)│ patterns) │ exec)   │  + coverage gaps) │  │
│  ├─────────┼────────┴───────────┴─────────┴───────────────────┤  │
│  │   llm   │            agentic (LangGraph)                   │  │
│  │(LiteLLM │  StateGraph: execute → analyze → decide          │  │
│  │ wrapper)│      ↑__________________ generate ___________↓   │  │
│  ├─────────┴──────────────────────────────────────────────────┤  │
│  │       reports / exports     │   background_jobs            │  │
│  └────────────────────────────────────────────────────────────┘  │
│           │                  │                                   │
│  ┌────────▼─────┐   ┌───────▼──────────────────────┐             │
│  │  Postgres    │   │   LangGraph Checkpointer     │             │
│  │  (SQLAlch.)  │   │  (langgraph-checkpoint-      │             │
│  │              │   │     postgres, same DB)       │             │
│  └──────────────┘   └──────────────────────────────┘             │
└──────────────────────────────────────────────────────────────────┘
                              │ outbound HTTP (httpx)
                              ▼
       ┌─────────────────────────────────────────────┐
       │  Target APIs:                               │
       │   • VAmPI (vulnerable demo, Docker'd)       │
       │   • Bundled sample API (FastAPI)            │
       │   • User-supplied URL + OpenAPI spec        │
       └─────────────────────────────────────────────┘
```

### Architectural style

**Modular monolith**. Single deployable FastAPI process with strict internal module boundaries. Modules communicate via typed service-function calls, not HTTP. The boundaries are real enough to extract a service later (mentioned as future work in the demo), but we pay none of the distributed-systems cost up front.

Rejected alternatives:
- **Microservices** — premature complexity, doubles plumbing work, hurts debug-ability during the vacation gap.
- **Event-driven (Celery + Redis)** — overkill at one-user POC scale; FastAPI `BackgroundTasks` handles all our async needs.

---

## 4. Module Structure

| Module | Purpose | Key dependencies |
|---|---|---|
| `auth` | JWT issue/verify, user CRUD, password hashing | `passlib[bcrypt]`, `python-jose` |
| `specs` | Upload + parse OpenAPI 3.x, extract endpoints | `prance`, `openapi-spec-validator` |
| `llm` | Provider-agnostic LLM client + structured-output helper | `litellm`, `pydantic` |
| `generator` | Compose prompt with few-shot patterns → call LLM → validate → persist `Test` rows | `app.llm` |
| `runner` | Execute tests via `httpx`, evaluate assertions, persist `TestResult` | `httpx`, `jsonpath-ng` |
| `analyzer` | LLM failure explanation + coverage gap detection | `app.llm` |
| `agentic` | LangGraph `StateGraph` orchestrating the closed loop | `langgraph`, `langgraph-checkpoint-postgres` |
| `reports` | Aggregate stats, export to JSON/HTML | `jinja2` |
| `background_jobs` | Thin wrapper around FastAPI `BackgroundTasks` for long ops | — |

### Why no `rag` module

Briefly considered for storing test pattern embeddings; rejected after design review. GPT-class models already know pytest/HTTP testing well; a curated ~6-pattern library fits directly into the prompt as few-shot examples (`app/generator/patterns/*.yaml`). ChromaDB adds setup, retrieval tuning, and a new failure mode for negligible quality improvement. See ADR-002 for full reasoning (to be written in W6).

---

## 5. Data Model

### Tables (10)

```text
users          (id, email UNIQUE, password_hash, name, created_at)
projects       (id, user_id FK, name, description, target_base_url, created_at)
specs          (id, project_id FK, version, raw_content JSONB, parsed_at, created_at)
endpoints      (id, spec_id FK, method, path, summary,
                parameters JSONB, request_body JSONB, responses JSONB)
test_suites    (id, project_id FK, spec_id FK, name, status,
                current_generation_depth INT DEFAULT 0,
                auto_loop_enabled BOOLEAN DEFAULT true,
                auto_loop_max_depth INT DEFAULT 3,
                auto_loop_max_tests_per_cycle INT DEFAULT 5,
                created_at, updated_at)
tests          (id, test_suite_id FK, endpoint_id FK,
                name, description, scenario_type,           -- positive/negative/security/boundary
                method, path, path_params JSONB, query_params JSONB,
                headers JSONB, body JSONB,
                expected_status INT, assertions JSONB,
                auto_generated BOOLEAN DEFAULT false,
                parent_coverage_gap_id FK NULL,
                generation_depth INT DEFAULT 0,
                generation_hash VARCHAR(64) NULL,           -- SHA-256 dedup hash
                created_at, updated_at)
                UNIQUE(test_suite_id, generation_hash)      -- DB-level dedup safeguard
runs           (id, test_suite_id FK, target_base_url,
                status,                                      -- pending/running/completed/error
                summary JSONB,                               -- {total, passed, failed, errors}
                parent_run_id FK NULL,
                loop_iteration INT DEFAULT 0,                -- 0 = user-triggered, 1+ = nth auto
                started_at, completed_at)
test_results   (id, run_id FK, test_id FK, status,           -- passed/failed/error/skipped
                response_status INT, response_headers JSONB, response_body JSONB,
                duration_ms INT,
                assertion_results JSONB,                     -- per-assertion outcomes
                error_message TEXT,
                created_at)
ai_analyses    (id, test_result_id FK UNIQUE,
                explanation, likely_cause, suggested_fix,
                created_at)
coverage_gaps  (id, test_suite_id FK, endpoint_id FK,
                scenario_description, severity,              -- low/medium/high
                spawned_test_id FK NULL,                     -- set when a test is auto-generated
                created_at)
```

All tables: `id` is UUID PK, `created_at` and `updated_at` are `TIMESTAMPTZ` with sensible defaults.

### Assertion type schema (inside `tests.assertions` JSONB)

```json
[
  {"type": "status_eq",         "expected": 200},
  {"type": "json_path",         "target": "$.id",        "op": "exists"},
  {"type": "json_path",         "target": "$.email",     "op": "eq", "expected": "x@y.z"},
  {"type": "body_contains",     "expected": "error"},
  {"type": "header_eq",         "target": "Content-Type", "expected": "application/json"},
  {"type": "response_time_lt",  "expected": 2000}
]
```

---

## 6. Key User Journeys

### Journey 1 — Spec → Generated Tests

```
[User] POST /projects/{id}/specs       (multipart, OpenAPI YAML/JSON)
   │
[specs] validate → parse → INSERT Spec + Endpoint rows
   │
[User] POST /test-suites {spec_id, endpoint_ids, scenarios}
   │
[BackgroundTask: generator.run()]
   │   for each (endpoint, scenario):
   │     • assemble prompt: system + few-shot patterns + endpoint detail
   │     • litellm.acompletion(response_format=GeneratedTest schema)
   │     • validate path/params against source endpoint
   │     • INSERT Test row
   │
TestSuite.status: pending → generating → ready
   │
[User] GET /test-suites/{id}/tests     → JSON-viewer cards
```

### Journey 2 — Run + Closed Agentic Loop

```
[User] POST /runs {test_suite_id, target_base_url}
   │
[runner.execute_run]      (async, BackgroundTask)
   1. async with httpx.AsyncClient():
        for test in tests:
          • resolve path placeholders
          • send HTTP request, capture (status, headers, body, duration)
          • evaluate assertions → assertion_results
          • INSERT TestResult
   2. UPDATE Run: status=completed, summary=...
   │
[agentic_loop.ainvoke(state)]      (LangGraph)
   ┌──────────────────────────────────────────────────────────────┐
   │  START → execute_run_node                                    │
   │            │                                                 │
   │            ▼                                                 │
   │          analyze_node    (LLM failure analysis + coverage)   │
   │            │                                                 │
   │            ▼                                                 │
   │          decide_continue  ──── "stop" ────►  END             │
   │            │                                                 │
   │            │ "continue"                                      │
   │            ▼                                                 │
   │          generate_node    (new tests for high-severity gaps) │
   │            │                                                 │
   │            └────────► execute_run_node    (loop back)        │
   └──────────────────────────────────────────────────────────────┘
   Termination conditions in decide_continue:
     • current_depth >= max_depth (default 3, hard cap 5)
     • no high-severity gaps in last analysis
```

### Journey 3 — On-Demand Coverage Analysis

The same coverage logic from the loop is also exposed at `POST /test-suites/{id}/coverage-analyze` for users who want to analyze without re-running.

---

## 7. The Agentic Loop in Detail

### `AgenticLoopState` (TypedDict)

```python
class AgenticLoopState(TypedDict):
    test_suite_id: UUID
    target_base_url: str
    current_depth: int                  # starts at 0
    max_depth: int                      # from suite config
    max_tests_per_cycle: int            # from suite config
    last_run_id: UUID | None
    last_gaps: list[dict]               # serializable form of CoverageGap
    new_test_ids: list[UUID]            # tests created in this iteration
    total_tokens_used: int              # accumulating LLM token usage
    final_status: Literal[
        "completed", "max_depth_hit", "no_high_gaps", "error"
    ] | None
```

### Nodes

| Node | Reads | Writes | Notes |
|---|---|---|---|
| `execute_run_node` | `test_suite_id`, `target_base_url`, `new_test_ids` (if iteration > 0) | creates new `Run`, inserts `TestResult` rows; returns `{last_run_id, current_depth+1}` | First iteration runs all tests; subsequent iterations run only tests where `generation_depth == current_depth` |
| `analyze_node` | `last_run_id` | calls `analyze_coverage_gaps(db, suite_id, run_id)` passing `last_run_id`; inserts `AIAnalysis` (per failed result) + `CoverageGap` rows; returns `{last_gaps}` | Two distinct LLM calls: failure analysis (small, per-failure) + coverage analysis (one large, per-run). Coverage analysis receives actual Test records and TestResult data so the LLM reasons from evidence, not guesses. |
| `generate_node` | `last_gaps`, `max_tests_per_cycle` | inserts new `Test` rows with `auto_generated=true`, `parent_coverage_gap_id`, `generation_depth=current_depth`, `generation_hash`; returns `{new_test_ids}` | Caps at `max_tests_per_cycle` high-severity gaps; computes SHA-256 of `endpoint_id:scenario_type:description.strip().lower()`, skips if hash exists in suite. `UniqueConstraint(test_suite_id, generation_hash)` as DB safeguard. |
| `finalize_node` | `current_depth`, `max_depth`, `total_tokens_used`, `last_gaps` | returns `{final_status}` | Terminal node that sets the final status based on why the loop stopped. Routes to `END`. |

### `decide_continue` (conditional edge function — pure, no state mutation)

`decide_continue` is a LangGraph routing function. It **must be pure** — it returns a routing key string and must **not** mutate state. Terminal status is set by `finalize_node`, not the routing function.

```python
def decide_continue(state: AgenticLoopState) -> Literal["continue", "finalize"]:
    """Pure routing function. Returns a routing key only. Does NOT mutate state."""
    if state["current_depth"] >= min(state["max_depth"], 5):     # hard cap
        return "finalize"
    if state["total_tokens_used"] >= 200000:                     # token budget
        return "finalize"
    high = [g for g in state["last_gaps"] if g["severity"] == "high"]
    if not high:
        return "finalize"
    return "continue"
```

### Checkpointing

`PostgresSaver` from `langgraph-checkpoint-postgres` persists `AgenticLoopState` after each node transition. If the server crashes mid-loop, calling `agentic_loop.ainvoke(...)` with the same `thread_id` resumes from the last checkpoint. This durability is part of the demo narrative.

### Safety caps (non-negotiable, hard-coded)

- `max_depth` ≤ 5
- `max_tests_per_cycle` ≤ 10
- `total_tokens_used` budget per suite (default 200k) → soft warn at 80%, hard stop at 100%
- Dedup hash (`generation_hash` column + unique constraint) prevents same-gap regeneration

---

## 8. Tech Stack (verified current stable versions)

### Backend

| Concern | Choice | Current stable |
|---|---|---|
| Web framework | FastAPI | 0.128.0 |
| Python | 3.11 | (mature, has `asyncio.TaskGroup`) |
| ORM + migrations | SQLAlchemy 2.0 (async) + Alembic | latest |
| Validation | Pydantic v2 | latest |
| HTTP client | httpx (async) | latest |
| **LLM router** | **LiteLLM** | **1.83.3-stable** |
| **Agentic orchestration** | **LangGraph** | **1.0.8** |
| Graph checkpointer | langgraph-checkpoint-postgres | matches langgraph 1.x |
| OpenAPI parsing | prance + openapi-spec-validator | latest |
| JSONPath | jsonpath-ng | latest |
| Auth | python-jose (JWT) + passlib[bcrypt] | latest |
| Logging | structlog (JSON output) | latest |
| Background tasks | FastAPI `BackgroundTasks` | (no Celery) |
| Lint + types | ruff + mypy --strict on `app/` | latest |
| Test runner (ours) | pytest + pytest-asyncio + httpx ASGI | latest |

### Frontend

| Concern | Choice |
|---|---|
| Framework | React 18 + TypeScript + Vite |
| Routing | React Router v6 |
| Server state | TanStack Query v5 |
| UI primitives | shadcn/ui + Tailwind CSS |
| Forms | react-hook-form + zod |
| JSON viewer | react-json-view-lite |
| Charts / tree | Recharts (charts), react-flow (lineage tree) |
| Auth state | Zustand |

### Infrastructure

| Concern | Choice |
|---|---|
| Containerization | Docker + docker-compose |
| Dev DB | SQLite file (zero setup), Postgres in compose for integration |
| Prod DB | Postgres 16 |
| Cloud target | Render free tier (Railway/Fly.io acceptable alternatives — decided W7) |
| Secrets | `.env` locally, platform env vars in prod |
| CI | GitHub Actions: ruff + mypy + pytest on PR |

> **Convention:** before pinning any version in `pyproject.toml` or `package.json`, verify current stable via Context7 / npm registry / PyPI. Training-data version numbers are stale.

---

## 9. Repository Structure

```
api-test-platform/   (== C:\test_claude_code)
├── README.md
├── docker-compose.yml             # backend + db + frontend + vampi (dev)
├── docker-compose.prod.yml        # prod overlay
├── .env.example
├── .github/workflows/ci.yml       # ruff + mypy + pytest on PR
│
├── docs/
│   ├── architecture.md            # narrative + final diagrams (W6-7)
│   ├── api.md                     # high-level API overview
│   ├── adr/                       # Architecture Decision Records
│   │   ├── 001-modular-monolith.md
│   │   ├── 002-no-rag-few-shot-instead.md
│   │   ├── 003-data-driven-tests.md
│   │   ├── 004-langgraph-for-agentic-loop.md
│   │   ├── 005-litellm-for-provider-portability.md
│   │   └── 006-jwt-auth-poc-scope.md
│   ├── specs/
│   │   └── 2026-05-14-api-test-platform-design.md   ← this file
│   └── plans/
│       ├── week-01-foundation-and-auth.md
│       ├── week-02-spec-ingestion.md
│       ├── week-03-llm-and-generation.md
│       ├── week-04-runner-and-failure-analysis.md
│       ├── week-05-agentic-loop.md
│       ├── week-06-07-vacation-docs.md
│       └── week-08-deploy-and-demo.md
│
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/versions/
│   ├── Dockerfile
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── deps.py
│   │   ├── auth/             {router,service,deps}.py + tests/
│   │   ├── specs/            {router,service,parser}.py + tests/
│   │   ├── llm/              {client,models}.py + tests/
│   │   ├── generator/        {router,service,prompts,schemas}.py
│   │   │                     + patterns/{positive,negative,auth_bypass,
│   │   │                                  bola,boundary,injection}.yaml
│   │   │                     + tests/
│   │   ├── runner/           {router,service,executor,assertions}.py + tests/
│   │   ├── analyzer/         {router,failure_analysis,coverage_analysis,
│   │   │                      prompts,schemas}.py + tests/
│   │   ├── agentic/          {state,nodes,guards,graph,checkpointer}.py + tests/
│   │   └── reports/          {router,export}.py + tests/
│   └── seeds/
│       └── sample_specs/     # VAmPI spec, bundled demo API spec
│
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── Dockerfile
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api/                   # TS client + TanStack Query hooks
│       ├── components/
│       │   ├── ui/                # shadcn primitives
│       │   ├── TestCard.tsx
│       │   ├── RunLineageTree.tsx
│       │   ├── AssertionList.tsx
│       │   ├── AIAnalysisPanel.tsx
│       │   └── CoverageGapList.tsx
│       ├── pages/
│       │   ├── Login.tsx
│       │   ├── Register.tsx
│       │   ├── Dashboard.tsx
│       │   ├── ProjectDetail.tsx
│       │   ├── SpecUpload.tsx
│       │   ├── EndpointExplorer.tsx
│       │   ├── TestSuiteDetail.tsx
│       │   ├── RunDetail.tsx
│       │   └── CoverageReport.tsx
│       ├── hooks/
│       └── styles/
│
└── sample-api/                    # bundled FastAPI demo target (not the platform)
    ├── main.py
    ├── openapi.json
    └── Dockerfile
```

---

## 10. Phase Plan (8 Weeks)

### Cadence

| Weeks | Mode | Hours/wk | Focus |
|---|---|---|---|
| 1-5 | Heavy build | 35-45 | Entire MVP, end W5 = working closed agentic loop |
| 6-7 | Vacation, no code | 2-5 | Architecture diagram + ADRs + docs |
| 8 | Return, ship | 30-35 | Polish, deploy live, record demo, present |

### Verification gates

| Wk | End-of-week demo gate |
|----|-----------------------|
| 1 | `docker compose up` → register → login → authenticated dashboard placeholder |
| 2 | Upload VAmPI `openapi.json` → see endpoints listed with method/path |
| 3 | Select endpoints → click Generate → 9-15 AI-generated structured tests visible |
| 4 | Click Run → live results → click failed test → LLM-written explanation visible |
| 5 | **Click Run → loop auto-runs 2-3 iterations → lineage tree shows new tests discovered without user clicks** |
| 6-7 | Architecture diagram + 6 ADRs committed; no code commits |
| 8 | Live URL accessible + recorded demo video + slide deck |

Detailed weekly plans live in `docs/plans/week-{NN}-*.md` — generated alongside this design.

---

## 11. Risks & Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| LLM token costs spiral in agentic loop | High | Per-run `total_tokens_used` cap, default `gpt-4o-mini`, gpt-4o only for generation; surface usage in UI |
| Generated tests reference paths/params not in spec | High | Validate `GeneratedTest` against source `Endpoint` *before* DB insert; retry once with feedback |
| Agentic loop runs away or duplicates work | High | Hard cap `max_depth=5`, `max_tests_per_cycle=10`, hash-dedupe on `(endpoint_id, scenario_type, normalized_description)` |
| Vacation gap erodes momentum | Medium | "No code commits" rule; structured doc-only work in ~2-hour chunks |
| LangGraph learning curve > planned | Medium | W5 Day 1: build a throwaway 2-node graph to internalize the API |
| VAmPI quirks during demo | Medium | Pin docker-compose to a specific VAmPI image tag; bundled sample API as fallback |
| Cloud deploy surprises in W8 | Medium | `docker-compose.prod.yml` validated locally end of W5; Render dry-run pre-vacation |
| Demo recording day glitches | Low | Record rough demo in W7 vacation week as backup; polished version W8 |

---

## 12. Tiered Scope

### MUST (W1-W5, MVP, non-negotiable)
- Auth (JWT)
- Spec upload + endpoint browse
- LLM-driven structured test generation
- httpx runner + 5 assertion types
- AI failure analysis
- Coverage gap analysis (on-demand + auto-in-loop)
- Full agentic loop (LangGraph + Postgres checkpointer)
- Read-only test UI (JSON view of generated tests)

### SHOULD (W8 polish, strong intent)
- docker-compose.prod + live cloud deploy
- Recorded demo video
- Reports/exports (JSON download)
- Run lineage tree visualization
- 6 ADRs + architecture doc

### NICE (W8 if time, otherwise "future work")
- Form-based test editor (vs. JSON view)
- HTML report export
- JUnit XML export (CI/CD integration angle)
- Mermaid auto-rendered LangGraph diagram served by the app
- Server-Sent Events for live loop streaming

### CUT (first to drop if behind)
- Form-based test editor → JSON view is fine
- HTML export → JSON is fine
- Spec versioning UI → assume one spec per project
- Run lineage as fancy graph → simple parent-link list

---

## 13. Demo Plan (5 minutes)

1. **0:00-0:30** — Problem framing: "Manual API testing is slow, shallow, and rarely finds security issues."
2. **0:30-1:00** — Register, login, see dashboard.
3. **1:00-1:45** — Upload VAmPI's `openapi.json`, browse endpoints.
4. **1:45-2:30** — Click Generate → structured tests appear. Call out LiteLLM (provider-agnostic) + Pydantic-schema structured outputs.
5. **2:30-4:00** — **The agentic loop.** Click Run, watch the lineage tree grow as iterations happen, point at a test the platform *invented after observing the first run* that reveals a real VAmPI BOLA/IDOR issue.
6. **4:00-4:30** — Show AI failure analysis + coverage gaps panel.
7. **4:30-5:00** — Architecture slide (LangGraph state machine viz), call out future work, "questions?"

---

## 14. Open Questions (Deferred to Implementation)

These do not block design approval. We decide in flight:

- Exact model selection per task — calibrate W3 (`gpt-4o-mini` default; `gpt-4o` for generation if quality matters).
- Test-edit UX — JSON view in MVP, form editor only if W8 has time.
- SSE vs. polling for live updates — polling in MVP, SSE only if < 1 day in W5.
- Final cloud provider — pick during W7 doc work based on free-tier comparison.
- Demo's target API — VAmPI primarily; bundled sample API fallback.
- Whether to render `graph.get_graph().draw_mermaid_png()` in-app for the demo.

---

## 15. Living Document Principle

This document captures the **current best understanding** of the system, not a contract. Expect changes:

- **For significant pivots** (e.g., swapping LiteLLM for direct provider SDK, replacing LangGraph, dropping a major feature): write a new ADR in `docs/adr/`, link to it from the Change History above, update the affected section in this doc with a brief note. Do not silently rewrite history.
- **For minor adjustments** (renaming a module, tweaking a table column, swapping a library version): edit in place, add a Change History row.
- **The 8-week plan is a target, not a schedule.** Slippage in any single week compresses the next week, not the MVP date. The MVP-by-W5 deadline is the immovable anchor.

---

## Appendix A — Decisions made in design conversation (compressed log)

- Scope = full lifecycle (generate + execute + report), not generation-only.
- Fresh start in `C:\test_claude_code`, ignoring prior sentiment-app `CLAUDE.md`.
- LLM provider for development = OpenAI, but **system is provider-agnostic via LiteLLM** to allow future switching.
- Test framework target = none — data-driven JSON tests executed by httpx (replaced earlier pytest+subprocess plan).
- Database = SQLite dev, Postgres prod.
- Vector DB = dropped after design review; few-shot patterns inline in prompt instead.
- Auth = JWT with email+password user accounts.
- Deployment = Docker Compose + live cloud deploy (Render default).
- Architecture style = modular monolith.
- Agentic loop = full closed loop (auto-runs new tests, not "stop and wait for user").
- Agentic orchestration = LangGraph (after user suggestion + reassessment).
- AI features beyond generation = failure analysis + coverage gap analysis (both confirmed).
- Demo target API = VAmPI (deliberately vulnerable Flask API).
- Cadence = 5 heavy + 2 vacation + 1 return.

---

*End of design specification.*
