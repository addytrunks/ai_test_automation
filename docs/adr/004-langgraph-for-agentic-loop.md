# ADR 004: LangGraph for Agentic Loop Orchestration

## Status
Accepted

## Date
2026-06-02

## Context
The core innovation of this platform is the **agentic loop** — a cycle of `execute → analyze → decide → generate` that iteratively improves test coverage. After executing tests, the analyzer identifies coverage gaps (e.g., missing security scenarios), and the generator creates new tests to address them. This cycle repeats until coverage is satisfactory or safety caps are hit.

We needed to decide how to orchestrate this loop:

1. **Custom while-loop implementation** — hand-rolled Python.
2. **LangGraph StateGraph** — a graph-based state machine from the LangChain ecosystem.

## Decision
Use **LangGraph's StateGraph** to define the agentic loop as a compiled graph with four nodes (`execute_run`, `analyze`, `generate`, `finalize`) and a conditional routing edge (`decide_continue`).

The graph definition (`app/agentic/graph.py`):
```
START → execute_run → analyze → [decide_continue] → generate → execute_run (loop)
                                                   → finalize → END
```

State is carried in a `TypedDict` (`AgenticLoopState`) with fields for depth tracking, gap data, token budget, and generated test IDs.

## Alternatives Considered

### Custom While-Loop Implementation

A custom implementation would look like:

```python
async def run_agentic_loop(suite_id, target_url, max_depth=3, max_tests=5):
    state = {"depth": 0, "total_tokens": 0}
    while state["depth"] < max_depth:
        run_id = await execute_tests(suite_id, target_url, state)
        gaps = await analyze_results(run_id)
        if not any(g["severity"] == "HIGH" for g in gaps):
            break
        new_tests = await generate_tests(suite_id, gaps, max_tests)
        state["depth"] += 1
        state["total_tokens"] += token_count
    return state
```

What we'd have to build manually:
- **State serialization:** Save/restore loop state to the database for crash recovery. Requires custom schema + serialization logic (~100-150 LOC).
- **Depth tracking:** Manual counter management with guard clauses at every step.
- **Error boundaries:** Try/except around each phase with cleanup logic to avoid orphaned runs.
- **Graph visualization:** No built-in way to visualize the loop structure for documentation or demos.
- **Estimated cost:** 2-3 additional development days for a production-ready version with proper error handling and state persistence.

### LangGraph Costs (Honest Assessment)

LangGraph is not free of friction:

1. **Additional runtime dependency:** `psycopg3` (via `langgraph-checkpoint-postgres`) is required for the checkpointer, which is **distinct from** the application's `asyncpg` driver. This means two separate PostgreSQL driver libraries coexist in the dependency tree — `asyncpg` for the app's async ORM queries and `psycopg3` for LangGraph's synchronous checkpoint operations (see `CHECKPOINTER_URL` in settings).

2. **Opaque control flow:** Routing logic lives in edge functions (`decide_continue`) rather than visible `if/else` blocks in a linear code path. Debugging requires understanding how LangGraph compiles the graph, serializes state between nodes, and dispatches to the next node based on edge return values.

3. **Internal complexity:** The checkpoint schema (thread_id, checkpoint_id, parent_id, metadata JSONB) is managed by LangGraph's internal migration system, separate from the app's Alembic migrations. Debugging state issues requires inspecting LangGraph's `checkpoints` table directly.

4. **Version coupling:** LangGraph's API surface (e.g., `set_entry_point()` → `add_edge(START, ...)` deprecation between 0.x and 1.x) means framework upgrades may require code changes to the graph definition.

### Why the Costs Are Acceptable

This decision is made specifically in the context of a **proof-of-concept** built over an 8-week internship:

- **Demo narrative:** LangGraph provides a standard vocabulary ("state graph", "nodes", "edges", "checkpointing") that communicates architectural sophistication in a mentor review and demo. The graph structure is directly presentable.
- **Built-in checkpointing:** Even a basic implementation gives us crash-recovery for free — if the loop fails mid-iteration, it can resume from the last checkpoint. Building this from scratch is not worth the POC timeline.
- **Safety caps are trivial:** Depth limits, token budgets, and test-per-cycle caps are naturally expressed as state fields checked in the `decide_continue` edge function.
- **Production tradeoff:** For a production system at scale with strict performance requirements, the custom while-loop would likely be preferable — fewer dependencies, fully transparent control flow, and no framework coupling. For this POC, the tradeoff favors LangGraph.

## Consequences

### Positive
- **Structured state management:** The `AgenticLoopState` TypedDict enforces a clear contract between nodes. Each node reads from and writes partial updates to a well-defined state shape.
- **Crash recovery:** The PostgreSQL checkpointer persists state after every node execution, enabling resume-on-failure.
- **Composability:** New nodes (e.g., a future "prioritize_gaps" step) can be added to the graph without restructuring the loop logic.
- **Visualization:** The compiled graph can be exported as a Mermaid diagram for architecture documentation.

### Negative
- **Dual PostgreSQL drivers:** `asyncpg` (app) + `psycopg3` (checkpointer) coexist. This is a known friction point but does not cause runtime conflicts.
- **Debugging overhead:** Graph compilation and state serialization add layers of abstraction that complicate step-through debugging compared to a simple while-loop.
- **Framework lock-in:** Switching away from LangGraph would require rewriting the loop orchestration. This is acceptable for a POC but would be a concern for a long-lived production system.
