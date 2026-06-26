# Week 6-7 Implementation Plan — Vacation & Documentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide documentation coverage for the POC while taking a break from code. You will complete the 6 required Architecture Decision Records (ADRs) and formalize the final architecture document. 

**Rule:** NO CODE COMMITS ARE ALLOWED IN THIS PERIOD. Only markdown changes in `docs/` and `README.md`.

**Verification gate:** 6 ADRs exist in `docs/adr/`. `docs/architecture.md` is complete with Mermaid diagrams showing the LangGraph state machine and the monolith components.

---

## File Structure for Week 6-7

**Repo root (`C:\AI_TEST_AUTOMATION\`):**
- Modify: `docs/architecture.md` (Create and populate)
- Create: `docs/api.md`
- Create: `docs/adr/002-no-rag-few-shot-instead.md`
- Create: `docs/adr/003-data-driven-tests.md`
- Create: `docs/adr/004-langgraph-for-agentic-loop.md`
- Create: `docs/adr/005-litellm-for-provider-portability.md`
- Create: `docs/adr/006-jwt-auth-poc-scope.md`

---

## Task 1: Complete ADR 002

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\docs\adr\002-no-rag-few-shot-instead.md`

- [x] **Step 1: Write ADR-002**

Write the ADR detailing why RAG (Vector DB) was rejected in favor of inline few-shot YAML patterns. Use the standard template:
- **Status:** Accepted
- **Date:** YYYY-MM-DD
- **Context:** We evaluated using a Vector DB to retrieve test patterns based on endpoint similarities. However, GPT-class models understand API testing well enough. A vector DB adds unnecessary setup and retrieval tuning overhead for minimal gain.
- **Decision:** Use inline few-shot YAML patterns injected directly into the prompt.
- **Alternatives Considered:** ChromaDB, pgvector, Pinecone.
- **Consequences:** Easier deployment, no retrieval tuning needed, bounded context length.

- [ ] **Step 2: Commit**
```bash
git add docs/adr/002-no-rag-few-shot-instead.md
git commit -m "docs: add ADR-002 justifying few-shot prompting over RAG"
```

---

## Task 2: Complete ADRs 003, 004, 005, 006

**Files:**
- Create remaining ADR files in `docs/adr/`.

Ensure each ADR uses the standard template (Status, Date, Context, Decision, Alternatives Considered, Consequences).

- [x] **Step 1: Write ADR-003**
Topic: Data-driven Tests (`003-data-driven-tests.md`). Justify using structured JSON for tests rather than executing generated python/pytest code (avoids arbitrary code execution risks, easier to parse and display).

- [x] **Step 2: Write ADR-004**
Topic: LangGraph for Agentic Loop (`004-langgraph-for-agentic-loop.md`). This ADR must include an **honest tradeoffs section** — shallow "pros only" ADRs fail mentor review. Specifically:

  **(a) Alternative: Custom while-loop implementation.** Describe what this would look like concretely: a `while depth < max_depth` loop calling `execute()`, `analyze()`, `generate()` in sequence. Enumerate what you'd have to build yourself: state serialization to DB for resume-on-crash, manual depth tracking, explicit error-boundary handling, and no built-in graph visualization. Estimate the additional code cost (rough LOC or days).

  **(b) LangGraph costs.** Be honest about what LangGraph introduces: `psycopg3` as a separate runtime dependency (distinct from the app's `asyncpg` driver — see `CHECKPOINTER_URL` in Week 5 Task 4), less transparent control flow (routing logic is implicit in edge functions rather than visible in a linear code path), and debugging requires understanding LangGraph internals (state serialization format, checkpoint schema, graph compilation). These are real friction points.

  **(c) Why costs are acceptable.** Frame this specifically as a POC decision: the project's goal is to *demonstrate agentic patterns* for a mentor review and demo, not to minimize runtime dependencies. LangGraph provides checkpointing, visualization, and a standard vocabulary for describing agent architectures — all of which directly serve the demo narrative. For a production system at scale, the custom while-loop might be preferable; for this POC, the tradeoff favors LangGraph.

- [x] **Step 3: Write ADR-005**
Topic: LiteLLM for portability (`005-litellm-for-provider-portability.md`). Justify avoiding hardcoding OpenAI SDK to allow switching to Anthropic or local models without code changes.

- [x] **Step 4: Write ADR-006**
Topic: JWT Auth for POC (`006-jwt-auth-poc-scope.md`). Justify omitting OAuth/MFA for a pure POC context to save time.

- [ ] **Step 5: Commit**
```bash
git add docs/adr/
git commit -m "docs: add remaining ADRs 003 through 006"
```

---

## Task 3: Architecture Document

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\docs\architecture.md`

- [x] **Step 1: Write Document**
Create a comprehensive markdown file explaining the overall system. 
Include:
- The monolith modular breakdown.
- Data models.
- A Mermaid diagram showing the LangGraph state machine (execute -> analyze -> generate loop).
- A Mermaid diagram showing the Frontend -> Backend -> Target API communication.

- [x] **Step 2: Write API Document**
Create `docs/api.md` as a high-level overview of the backend REST API, documenting the core domain boundaries (`/projects`, `/specs`, `/test-suites`, `/runs`).

- [ ] **Step 3: Commit**
```bash
git add docs/architecture.md docs/api.md
git commit -m "docs: add comprehensive architecture and api documents"
```

---

## Task 4: Demo Prep

- [ ] **Step 1: Rough Demo Video**
Record a rough, 5-minute screencast of the POC working end-to-end as a backup for the final presentation.

- [ ] **Step 2: Slide Deck Outline**
Draft a 5-10 slide deck outline covering the problem, the agentic loop solution, architecture, and future work.

---

## Verification Checklist (end of Week 7)

- [x] `docs/adr/001-modular-monolith.md` exists (from W1).
- [x] `docs/adr/002-no-rag-few-shot-instead.md` exists.
- [x] `docs/adr/003-data-driven-tests.md` exists.
- [x] `docs/adr/004-langgraph-for-agentic-loop.md` exists.
- [x] `docs/adr/005-litellm-for-provider-portability.md` exists.
- [x] `docs/adr/006-jwt-auth-poc-scope.md` exists.
- [x] `docs/architecture.md` is complete and includes mermaid diagrams.
- [x] `docs/api.md` exists.
- [ ] Rough demo video recorded.
- [ ] Slide deck outline created.
- [x] **Zero code files (.py, .ts, .tsx) were modified.**

When all 11 boxes are ticked, you are done with Weeks 6 & 7.

---

## Notes for Week 8

Week 8 focuses on final polish, live deployment to a cloud PaaS, and finalizing the demo video and presentation.
