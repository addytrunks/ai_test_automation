# AI-Assisted API Test Generation Platform — Architecture Diagrams

> Prepared for mentor review — May 2026

---

## 1. System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                   React SPA  (Vite + TypeScript)                     │
│   Login │ Dashboard │ Specs │ Endpoints │ Tests │ Runs │ Reports     │
└───────────────────────────────┬──────────────────────────────────────┘
                                │  HTTPS + JWT (Bearer)
┌───────────────────────────────▼──────────────────────────────────────┐
│                    FastAPI Monolith  (app.main)                       │
│                                                                      │
│  ┌──────────┬─────────┬────────────┬──────────┬───────────────────┐  │
│  │   auth   │  specs  │  generator │  runner  │     analyzer      │  │
│  │  (JWT,   │ (parse  │  (LLM +    │ (httpx   │ (failure expl.    │  │
│  │  users)  │ OpenAPI)│  patterns) │  exec)   │  + coverage gaps) │  │
│  ├──────────┼─────────┴────────────┴──────────┴───────────────────┤  │
│  │   LLM    │              agentic (LangGraph)                    │  │
│  │ (LiteLLM │    StateGraph: execute → analyze → decide           │  │
│  │  wrapper)│         ↑________________ generate _________↓       │  │
│  ├──────────┴─────────────────────────────────────────────────────┤  │
│  │        reports / exports      │     background_jobs            │  │
│  └───────────────────────────────────────────────────────────────-┘  │
│            │                   │                                     │
└────────────┼───────────────────┼─────────────────────────────────────┘
             │                   │
     ┌───────▼─────────┐     ┌──────▼──────────┐  ┌───────────────────┐
     │  PostgreSQL DB  │     │  Target API     │  │  LLM Provider     │
     │  (SQLAlchemy    │     │  (e.g. VAmPI)   │  │  (OpenAI /        │
     │   2.0 async)    │     │                 │  │   Anthropic)      │
     └────────────────-┘     └─────────────────┘  └───────────────────┘
```

---

## 2. User Workflow

```
  ┌────────────┐     ┌────────────┐     ┌────────────┐     ┌────────────┐
  │  Register  │────▶│   Create   │────▶│   Upload   │────▶│   Browse   │
  │  & Login   │     │  Project   │     │  OpenAPI   │     │ Endpoints  │
  └────────────┘     └────────────┘     │   Spec     │     └─────┬──────┘
                                        └────────────┘           │
                                                                 ▼
  ┌────────────┐     ┌────────────┐                      ┌──────────────┐
  │   Export   │     │    All     │         No            │   Generate   │
  │   Report   │◀────│  Passed?   │◀─────────────┐       │  Tests via   │
  └────────────┘     └─────┬──────┘              │       │     AI       │
        ▲                  │ No                   │       └──────┬───────┘
        │                  ▼                      │              │
        │           ┌──────────────┐              │              ▼
        │           │   Agentic    │──────────────┘       ┌──────────────┐
        └───────────│    Loop      │◀─────────────────────│   Execute    │
            Yes     └──────────────┘                      │    Tests     │
                                                          └──────────────┘
```

---

## 3. Agentic Loop — The Core Innovation

```
                         ┌─────────────────────────────────────────┐
                         │           SAFETY CAPS                   │
                         │  • Max 5 iterations                     │
                         │  • Max 10 tests per cycle               │
                         │  • 200k token budget                    │
                         └──────────────────┬──────────────────────┘
                                            │
                                            ▼
                    ┌───────────────────────────────────────────┐
                    │                                           │
          ┌─────────▼──────────┐                               │
          │                    │                               │
          │   1. EXECUTE       │                               │
          │   Run all tests    │                               │
          │   against live API │                               │
          │                    │                               │
          └─────────┬──────────┘                               │
                    │                                          │
                    ▼                                          │
          ┌────────────────────┐                               │
          │                    │                               │
          │   2. ANALYZE       │                               │
          │   • Failure expl.  │                               │
          │   • Coverage gaps  │                               │
          │                    │                               │
          └─────────┬──────────┘                               │
                    │                                          │
                    ▼                                          │
          ┌────────────────────┐                               │
          │                    │                               │
          │   3. DECIDE        │                               │
          │   High-severity    │──── No gaps ────▶ ✅ DONE     │
          │   gaps remain?     │     or cap hit                │
          │                    │                               │
          └─────────┬──────────┘                               │
                    │ Yes                                      │
                    ▼                                          │
          ┌────────────────────┐                               │
          │                    │                               │
          │   4. GENERATE      │                               │
          │   AI creates new   │───────────────────────────────┘
          │   tests for gaps   │         Loop back to Execute
          │                    │
          └────────────────────┘
```

---

## 4. Data Model

```
  ┌──────────┐
  │   USER   │
  └────┬─────┘
       │ owns
       ▼
  ┌──────────┐        ┌──────────┐        ┌──────────────┐
  │ PROJECT  │───────▶│   SPEC   │───────▶│   ENDPOINT   │
  └────┬─────┘has     └──────────┘parsed  └───────┬──────┘
       │                                          │
       │ has                              targets │
       ▼                                          │
  ┌──────────────┐                                │
  │  TEST SUITE  │◀───────────────────────────────┘
  └──┬─────┬─────┘                         ┌──────────────────┐
     │     │                               │  COVERAGE GAP    │
     │     └──────────identifies──────────▶│  • severity      │
     │                                     │  • scenario desc │
     │ contains                            └──────────────────┘
     ▼
  ┌──────────┐
  │   TEST   │
  │ • method │
  │ • path   │
  │ • body   │
  │ • assert │
  └────┬─────┘
       │ executed in
       ▼
  ┌──────────┐
  │   RUN    │
  │ • status │
  │ • iter#  │
  └────┬─────┘
       │ produces
       ▼
  ┌──────────────┐        ┌────────────────┐
  │ TEST RESULT  │───────▶│  AI ANALYSIS   │
  │ • pass/fail  │explains│  • explanation │
  │ • duration   │        │  • fix suggest │
  └──────────────┘        └────────────────┘
```

---

## 5. Tech Stack

```
  ┌─────────────────────────────────────────────────────────────────┐
  │                    AI Test Generation Platform                  │
  ├─────────────┬─────────────┬──────────────┬─────────────────────┤
  │  FRONTEND   │  BACKEND    │  AI LAYER    │  INFRASTRUCTURE     │
  ├─────────────┼─────────────┼──────────────┼─────────────────────┤
  │ React 18    │ FastAPI     │ LiteLLM      │ PostgreSQL          │
  │ Vite        │ SQLAlchemy  │ LangGraph    │ Docker Compose      │
  │ TypeScript  │ Pydantic v2 │ Few-Shot     │ Render.com          │
  │ TanStack    │ Alembic     │ Patterns     │                     │
  │ Query v5    │ Uvicorn     │ Structured   │ Demo Target:        │
  │ React Flow  │ httpx       │ Outputs      │ VAmPI               │
  └─────────────┴─────────────┴──────────────┴─────────────────────┘
```
