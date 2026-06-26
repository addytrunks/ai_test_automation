# ADR 002: Few-Shot Prompting Over RAG (Vector DB)

## Status
Accepted

## Date
2026-05-21

## Context
When designing the test generation pipeline, we evaluated two main approaches for supplying the LLM with test pattern knowledge:

1. **Retrieval-Augmented Generation (RAG):** Store test patterns in a vector database (e.g., ChromaDB, pgvector, Pinecone), embed incoming endpoint descriptions, and retrieve the most semantically similar patterns at generation time.
2. **Inline Few-Shot Patterns:** Inject curated YAML test pattern examples directly into the LLM prompt, providing the model with explicit structure and scenario templates.

GPT-class models (GPT-4o, Claude 3.5, Gemini 1.5) already have strong understanding of API testing concepts — HTTP methods, status codes, authentication flows, injection vectors, and OWASP categories. The marginal gain from retrieval-based pattern matching does not justify the operational overhead for a POC.

## Decision
Use **inline few-shot YAML patterns** injected directly into the system prompt for test generation.

The generator module constructs prompts containing:
- The target endpoint's OpenAPI definition (method, path, parameters, request body, responses, security).
- 3-5 curated YAML examples demonstrating the expected output structure for positive, negative, and security test scenarios.
- Coverage gap context (if in agentic loop iteration > 0) to guide generation toward missing scenarios.

## Alternatives Considered

| Alternative | Reason for Rejection |
|---|---|
| **ChromaDB** | Adds an in-process vector store dependency. Requires embedding model setup, index management, and retrieval tuning. Overkill for ~50 test patterns. |
| **pgvector** | Leverages existing PostgreSQL but adds extension dependency, embedding pipeline, and similarity-search query complexity. |
| **Pinecone** | Managed service with per-query costs. Introduces external API dependency and network latency for every generation request. |

## Consequences

### Positive
- **Zero additional infrastructure:** No vector DB to deploy, configure, or maintain. The few-shot patterns live in the codebase as plain YAML strings.
- **Deterministic behavior:** The same patterns are always included in the prompt. No retrieval non-determinism or embedding drift.
- **Easier debugging:** Developers can read the full prompt to understand exactly what the model sees. No hidden retrieval layer.
- **Bounded context:** Pattern examples are curated to fit within the model's context window alongside the endpoint definition and gap context.

### Negative
- **Scalability ceiling:** If the pattern library grows beyond what fits in a single prompt's context window (~10-15 examples), we would need to adopt retrieval or dynamic selection. For this POC's scope (~5 scenario types), this is not a concern.
- **Manual curation:** Adding new pattern types requires editing the prompt template code rather than inserting a document into a database. This is acceptable for the POC timeline.
