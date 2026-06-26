# ADR 005: LiteLLM for LLM Provider Portability

## Status
Accepted

## Date
2026-05-21

## Context
The platform relies on Large Language Models for two core functions:

1. **Test generation:** Producing structured JSON test definitions from OpenAPI endpoint specifications and coverage gap context.
2. **Failure analysis:** Explaining why a test failed and suggesting fixes based on the request/response pair.

During development, we needed to switch between LLM providers (OpenAI GPT-4o, Google Gemini 1.5 Flash, Anthropic Claude 3.5 Sonnet, and local models via Ollama) depending on cost, rate limits, and availability. Hardcoding the OpenAI SDK would require rewriting API calls, authentication, and response parsing every time we switch providers.

## Decision
Use **LiteLLM** as a unified abstraction layer for all LLM interactions.

All LLM calls go through `litellm.acompletion()` with the model specified via the `LLM_MODEL` environment variable:
```python
# Switch providers by changing one env var:
LLM_MODEL=gpt-4o                    # OpenAI
LLM_MODEL=gemini/gemini-1.5-flash   # Google
LLM_MODEL=anthropic/claude-3.5-sonnet  # Anthropic
LLM_MODEL=ollama/llama3             # Local
```

The `app/llm/` module wraps LiteLLM calls with:
- Retry logic via `tenacity` for transient API failures.
- Token usage tracking for the agentic loop's budget cap.
- Structured output enforcement (JSON mode) for test generation.

## Alternatives Considered

| Alternative | Reason for Rejection |
|---|---|
| **OpenAI SDK directly** | Locks the project to a single provider. Switching to Gemini or Claude requires rewriting all API calls, auth headers, and response parsing. |
| **LangChain's ChatModel abstraction** | Heavier dependency with many sub-packages. LiteLLM is lighter and purpose-built for the exact problem (unified API across providers). We already use LangGraph but don't need LangChain's full model abstraction. |
| **Manual adapter pattern** | Writing our own `LLMProvider` interface with `OpenAIProvider`, `GeminiProvider`, etc. This is exactly what LiteLLM already provides, tested across 100+ providers. Reinventing it wastes POC time. |

## Consequences

### Positive
- **Provider agnostic:** Switching LLM providers requires changing a single environment variable. No code changes needed.
- **Cost optimization:** During development, we can use cheaper models (Gemini Flash) for iteration and switch to stronger models (GPT-4o) for final validation.
- **OpenRouter support:** LiteLLM natively supports OpenRouter, which provides a single API key for multiple providers with usage-based billing — ideal for a POC budget.
- **Future-proof:** New models (GPT-5, Gemini 2, etc.) are typically supported by LiteLLM within days of release.

### Negative
- **Abstraction leaks:** Some provider-specific features (OpenAI's function calling syntax vs. Anthropic's tool use format) may behave differently through the abstraction. We mitigate this by using only the common subset (chat completions with JSON mode).
- **Additional dependency:** LiteLLM pulls in several transitive dependencies. Acceptable for a POC; in production, a thinner custom wrapper might be preferred.
