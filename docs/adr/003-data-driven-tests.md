# ADR 003: Data-Driven Tests via Structured JSON

## Status
Accepted

## Date
2026-05-21

## Context
The platform needs to represent AI-generated test cases in a format that can be stored, executed, analyzed, and displayed in the frontend. Two approaches were considered:

1. **Executable code generation:** The LLM generates Python/pytest test functions that are executed directly.
2. **Structured data:** The LLM generates test definitions as structured JSON objects that are interpreted and executed by a generic runner engine.

Executing arbitrary LLM-generated code introduces severe security risks (arbitrary code execution, filesystem access, network exfiltration) and makes the test lifecycle harder to manage — tests become opaque code blobs rather than inspectable data.

## Decision
Use **structured JSON test definitions** that are stored in the database and executed by a deterministic runner engine.

Each test is a JSON-serializable record containing:
```json
{
  "method": "POST",
  "path": "/users/v1/register",
  "headers": {"Content-Type": "application/json"},
  "body": {"username": "test_user", "password": "weak"},
  "expected_status": 200,
  "assertions": [
    {"type": "status_eq", "expected": 200},
    {"type": "body_contains", "path": "$.message", "expected": "success"}
  ]
}
```

The runner uses `httpx` to execute each test against the target API based on the structured definition. Assertions are evaluated by a generic assertion engine, not by arbitrary code.

## Alternatives Considered

| Alternative | Reason for Rejection |
|---|---|
| **Python/pytest code generation** | Arbitrary code execution risk. Requires sandboxing (Docker containers, nsjail) to run safely. Tests become opaque — cannot be easily displayed, edited, or diffed in the UI. |
| **YAML test files (Karate/Tavern style)** | Similar to structured JSON but requires file I/O and a separate parser. JSON is natively supported by PostgreSQL (JSONB), SQLAlchemy, Pydantic, and the frontend — no translation layer needed. |
| **Postman collections** | Proprietary format with JavaScript scripting in pre/post hooks. Introduces vendor lock-in and the same code execution concerns. |

## Consequences

### Positive
- **Security:** No arbitrary code execution. The runner only performs HTTP requests and assertion checks — both well-bounded operations.
- **Transparency:** Every test is fully inspectable in the UI. Users can see exactly what request will be sent and what assertions will be checked.
- **Storage:** Tests are JSONB columns in PostgreSQL. They benefit from indexing, querying, and native JSON operators.
- **Diffing & Lineage:** Because tests are structured data, the platform can compute generation hashes for deduplication and track parent-child relationships (which coverage gap spawned which test).

### Negative
- **Expressiveness ceiling:** Some complex test scenarios (multi-step workflows, conditional logic, dynamic variable chaining) are harder to express in flat JSON. We mitigate this with `extract` and `static_context` fields for variable passing between setup and dependent tests.
- **Runner complexity:** The assertion engine must handle multiple assertion types (`status_eq`, `body_contains`, `json_path_eq`, etc.) rather than delegating to pytest's native assert. This is bounded and well-defined.
