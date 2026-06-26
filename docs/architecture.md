# Architecture Document

> AI-Assisted API Test Generation Platform — Architecture Overview

---

## 1. Overview

This platform is an AI-assisted API test generation system that automatically creates, executes, and iteratively improves API test suites. The core innovation is an **agentic loop** — a LangGraph-orchestrated cycle that executes tests, analyzes results for coverage gaps, and generates new tests to fill those gaps.

The system targets OpenAPI-defined APIs and produces structured JSON test cases covering positive, negative, and security scenarios (BOLA/IDOR, authentication bypass, injection attacks).

### Key Capabilities
- **OpenAPI ingestion:** Upload and parse OpenAPI 2.0/3.x specs to extract endpoints, parameters, and security schemes.
- **AI-powered generation:** LLM-driven test creation using few-shot prompting with structured JSON output.
- **Automated execution:** HTTP-based test runner with assertion evaluation against live target APIs.
- **Coverage analysis:** AI-powered gap detection identifying missing security scenarios per endpoint.
- **Agentic iteration:** Autonomous loop that generates new tests for discovered gaps until coverage is satisfactory or safety caps are hit.

---

## 2. Architecture Pattern: Modular Monolith

The system follows a **modular monolith** pattern (see [ADR-001](adr/001-modular-monolith.md)). A single FastAPI backend serves all domain functionality, organized into isolated modules with clear boundaries.

```mermaid
graph TB
    subgraph Frontend["Frontend (React SPA)"]
        UI[Vite + TypeScript + TanStack Query]
    end

    subgraph Backend["Backend (FastAPI Monolith)"]
        AUTH[auth]
        SPECS[specs]
        GEN[generator]
        RUN[runner]
        ANA[analyzer]
        AGENT[agentic<br/>LangGraph]
        LLM_MOD[llm<br/>LiteLLM wrapper]
    end

    subgraph Infrastructure
        PG[(PostgreSQL 16)]
        TARGET[Target API<br/>e.g. VAmPI]
        LLM_PROV[LLM Provider<br/>OpenAI / Gemini / Anthropic]
    end

    UI -->|HTTPS + JWT Bearer| Backend
    AUTH --> PG
    SPECS --> PG
    GEN --> PG
    GEN --> LLM_MOD
    RUN --> PG
    RUN --> TARGET
    ANA --> PG
    ANA --> LLM_MOD
    AGENT --> RUN
    AGENT --> ANA
    AGENT --> GEN
    LLM_MOD --> LLM_PROV
```

### Module Responsibilities

| Module | Directory | Responsibility |
|---|---|---|
| **auth** | `app/auth/` | User registration, login, JWT token issuance and validation |
| **specs** | `app/specs/` | Project CRUD, OpenAPI spec upload/parsing, endpoint extraction |
| **generator** | `app/generator/` | Test suite creation, LLM-driven test generation, deduplication |
| **runner** | `app/runner/` | Test execution via `httpx`, assertion evaluation, result recording |
| **analyzer** | `app/analyzer/` | Failure explanation, coverage gap detection via LLM |
| **agentic** | `app/agentic/` | LangGraph state machine orchestrating the execute→analyze→generate loop |
| **llm** | `app/llm/` | LiteLLM abstraction for provider-agnostic LLM calls |

---

## 3. Agentic Loop — The Core Innovation

The agentic loop is the platform's differentiator. Unlike one-shot test generators, this system **iteratively improves** test coverage through an autonomous feedback loop.

### LangGraph State Machine

```mermaid
stateDiagram-v2
    [*] --> execute_run: START

    execute_run --> analyze: Run all tests<br/>against live API

    analyze --> decide: Identify failures<br/>& coverage gaps

    state decide <<choice>>
    decide --> generate: HIGH severity<br/>gaps found
    decide --> finalize: No HIGH gaps<br/>or cap hit

    generate --> execute_run: New tests created<br/>Loop back

    finalize --> [*]: END<br/>Set final_status
```

### State Definition

The `AgenticLoopState` TypedDict carries context through each iteration:

```
AgenticLoopState:
  test_suite_id     — UUID of the test suite
  target_base_url   — Base URL of the target API
  current_depth     — Iteration counter (0-based)
  max_depth         — Hard cap (default: 3, max: 5)
  max_tests_per_cycle — Tests generated per iteration (default: 5, max: 10)
  last_run_id       — UUID of the most recent execution run
  last_gaps         — Coverage gaps from latest analysis
  new_test_ids      — Tests generated in current iteration only
  total_tokens_used — Cumulative LLM token spend (reducer: operator.add)
  final_status      — Terminal state reason
```

### Safety Caps
- **Max 5 iterations** — Prevents runaway loops.
- **Max 10 tests per cycle** — Bounds generation cost.
- **200K token budget** — Hard cap on cumulative LLM spend.

### Loop Behavior
1. **Depth 0:** Execute all tests in the suite (baseline).
2. **Depth > 0:** Execute only `new_test_ids` (tests generated in the previous iteration) to avoid redundant re-execution.
3. **Termination:** The loop ends when no HIGH-severity gaps remain, max depth is reached, or the token budget is exhausted.

---

## 4. Data Model

```mermaid
erDiagram
    USER ||--o{ PROJECT : owns
    PROJECT ||--o{ SPEC : has
    PROJECT ||--o{ TEST_SUITE : has
    SPEC ||--o{ ENDPOINT : parsed_into
    TEST_SUITE ||--o{ TEST : contains
    TEST_SUITE ||--o{ COVERAGE_GAP : identifies
    ENDPOINT ||--o{ TEST : targets
    TEST ||--o{ TEST_RESULT : "executed in"
    TEST_RESULT ||--o| AI_ANALYSIS : "explained by"
    RUN ||--o{ TEST_RESULT : produces
    RUN ||--o{ COVERAGE_GAP : discovers
    TEST_SUITE ||--o{ RUN : "has runs"

    USER {
        uuid id PK
        string email UK
        string password_hash
        string name
        datetime created_at
    }

    PROJECT {
        uuid id PK
        uuid user_id FK
        string name
        string description
        string target_base_url
    }

    SPEC {
        uuid id PK
        uuid project_id FK
        string version
        jsonb raw_content
        datetime parsed_at
    }

    ENDPOINT {
        uuid id PK
        uuid spec_id FK
        string method
        string path
        string summary
        jsonb parameters
        jsonb request_body
        jsonb responses
        jsonb security
    }

    TEST_SUITE {
        uuid id PK
        uuid project_id FK
        uuid spec_id FK
        string name
        string status
        int current_generation_depth
        bool auto_loop_enabled
        int auto_loop_max_depth
        int auto_loop_max_tests_per_cycle
    }

    TEST {
        uuid id PK
        uuid test_suite_id FK
        uuid endpoint_id FK
        string name
        string scenario_type
        string method
        string path
        jsonb body
        int expected_status
        jsonb assertions
        jsonb extract
        jsonb static_context
        bool auto_generated
        uuid parent_coverage_gap_id
        int generation_depth
        string generation_hash UK
    }

    RUN {
        uuid id PK
        uuid test_suite_id FK
        string target_base_url
        string status
        jsonb summary
        uuid parent_run_id FK
        int loop_iteration
    }

    TEST_RESULT {
        uuid id PK
        uuid run_id FK
        uuid test_id FK
        string status
        int response_status
        jsonb response_headers
        jsonb response_body
        int duration_ms
        jsonb assertion_results
        string error_message
    }

    AI_ANALYSIS {
        uuid id PK
        uuid test_result_id FK
        string explanation
        string likely_cause
        string suggested_fix
    }

    COVERAGE_GAP {
        uuid id PK
        uuid test_suite_id FK
        uuid endpoint_id FK
        uuid run_id FK
        string scenario_description
        string severity
        uuid spawned_test_id FK
    }
```

### Key Relationships
- **Test lineage:** `Test.parent_coverage_gap_id` → `CoverageGap.id` → `CoverageGap.spawned_test_id` creates a bidirectional link showing which gap triggered which test.
- **Run chaining:** `Run.parent_run_id` links iterations of the agentic loop, enabling lineage tree visualization.
- **Deduplication:** `Test.generation_hash` (unique per suite) prevents the LLM from generating duplicate tests across iterations.

---

## 5. Communication Flow

```mermaid
sequenceDiagram
    actor User
    participant FE as React Frontend
    participant BE as FastAPI Backend
    participant DB as PostgreSQL
    participant LLM as LLM Provider
    participant API as Target API

    User->>FE: Upload OpenAPI spec
    FE->>BE: POST /api/v1/projects/{id}/specs
    BE->>DB: Store spec + parse endpoints
    BE-->>FE: 201 Created (spec + endpoints)

    User->>FE: Generate tests
    FE->>BE: POST /api/v1/projects/{id}/test-suites/generate
    BE->>DB: Fetch endpoints from spec
    BE->>LLM: Generate test definitions (few-shot prompt)
    LLM-->>BE: Structured JSON tests
    BE->>DB: Store tests with generation_hash
    BE-->>FE: 201 Created (test suite)

    User->>FE: Start agentic loop
    FE->>BE: POST /api/v1/test-suites/{id}/runs (with loop)

    loop Agentic Loop (depth 0..N)
        BE->>API: Execute tests via httpx
        API-->>BE: HTTP responses
        BE->>DB: Store TestResults
        BE->>LLM: Analyze failures + find gaps
        LLM-->>BE: Explanations + CoverageGaps
        BE->>DB: Store AIAnalysis + CoverageGaps

        alt HIGH severity gaps found
            BE->>LLM: Generate new tests for gaps
            LLM-->>BE: New test definitions
            BE->>DB: Store new tests
            Note over BE: Loop continues
        else No HIGH gaps or cap hit
            Note over BE: Loop terminates
        end
    end

    BE-->>FE: Run complete (with results)
    User->>FE: View results, gaps, lineage
```

---

## 6. Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Frontend** | React 18, Vite, TypeScript | Single-page application |
| | TanStack Query v5 | Server state management & caching |
| | React Router v6 | Client-side routing |
| | shadcn/ui + Tailwind CSS | Component library & styling |
| | React Flow | Lineage tree visualization |
| **Backend** | FastAPI | Async web framework |
| | SQLAlchemy 2.0 (async) | ORM with asyncpg driver |
| | Pydantic v2 | Request/response validation |
| | Alembic | Database migrations |
| | Uvicorn | ASGI server |
| | httpx | Async HTTP client for test execution |
| **AI Layer** | LiteLLM | Provider-agnostic LLM abstraction |
| | LangGraph | Agentic loop state machine |
| | langgraph-checkpoint-postgres | Crash-recovery checkpointing |
| | psycopg3 | Checkpointer DB driver (separate from asyncpg) |
| **Infrastructure** | PostgreSQL 16 | Primary database (JSONB for structured test data) |
| | Docker Compose | Local development orchestration |
| | VAmPI | Intentionally vulnerable API for demo/testing |

---

## 7. Security Considerations

- **Authentication:** JWT-based with bcrypt password hashing (see [ADR-006](adr/006-jwt-auth-poc-scope.md)).
- **Authorization:** All data endpoints enforce ownership checks via `CurrentUser` dependency — users can only access their own projects, specs, and test results.
- **No arbitrary code execution:** Tests are structured JSON data interpreted by a deterministic runner, not executable code (see [ADR-003](adr/003-data-driven-tests.md)).
- **Target API isolation:** The runner executes HTTP requests against a user-specified `target_base_url`. In production, this should be validated and potentially sandboxed.

---

## 8. Deployment Architecture

### Local Development
```
docker-compose up -d          # PostgreSQL + VAmPI
uvicorn app.main:app --reload # Backend on :8000
npm run dev                   # Frontend on :5173
```

### Production (Planned)
- **Backend:** Docker container running Uvicorn behind a reverse proxy.
- **Frontend:** Static build served via Nginx or cloud CDN.
- **Database:** Managed PostgreSQL (e.g., Render PostgreSQL, Neon, Supabase).
- **Target API:** VAmPI deployed as a separate service for demo purposes.

---

## 9. Architecture Decision Records

| ADR | Title | Status |
|---|---|---|
| [001](adr/001-modular-monolith.md) | Modular Monolith Architecture | Accepted |
| [002](adr/002-no-rag-few-shot-instead.md) | Few-Shot Prompting Over RAG | Accepted |
| [003](adr/003-data-driven-tests.md) | Data-Driven Tests via Structured JSON | Accepted |
| [004](adr/004-langgraph-for-agentic-loop.md) | LangGraph for Agentic Loop | Accepted |
| [005](adr/005-litellm-for-provider-portability.md) | LiteLLM for Provider Portability | Accepted |
| [006](adr/006-jwt-auth-poc-scope.md) | JWT Auth Scoped to POC | Accepted |
