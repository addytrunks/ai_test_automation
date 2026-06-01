# Platform Refinement Tracker

This is a living document to track all pending refinements, prompt adjustments, and UI/backend enhancements as we move into Week 4 and beyond.

---

## 📋 Active Tasks & Refinements

### 1. Test Generation & Prompt Engineering

- [ ] **Fix Auth-Related Negative Tests**
  * **Issue:** When generating negative tests for "invalid tokens," the LLM often completely omits the HTTP headers instead of providing a bad token.
  * **Fix:** Update the `SYSTEM_PROMPT` in `service.py` to explicitly mandate: *"If you generate a test asserting 401 Unauthorized for an invalid token/signature, you MUST provide a malformed or invalid token in the Authorization header (e.g., `{"Authorization": "Bearer invalid_token"}`) rather than omitting the header entirely."*

- [ ] **Add Rate Limiting/Brute Force Scenario**
  * **Requirement:** Add support for detecting rate-limiting vulnerabilities (from user's work log notes).
  * **Fix:** Create a `rate_limiting.yaml` few-shot pattern. The generated test case should verify if multiple identical login/sensitive requests return `429 Too Many Requests` or require standard assertions testing status code thresholds.

---

### 2. User Interface & Configuration (Week 4 Focus)

- [ ] **Manual Auth Endpoint Selector in UI**
  * **Requirement:** If the backend detection heuristic fails (finds 0 or 2+ candidates) and throws a 400, the UI must display a dropdown allowing the user to manually select which endpoint is the authentication route.
  * **Fix:**
    * Update the `/projects/{id}/test-suites` endpoint payload schema to accept an optional `auth_endpoint_id` directly from the frontend.
    * Update the Endpoint Explorer UI to present an auth dropdown when a mismatch or failure occurs.

- [ ] **Clean Render for Missing Headers/Bodies**
  * **Issue:** If headers or body dictionaries are missing/null, the detail cards can look empty.
  * **Fix:** Update `TestSuiteDetail.tsx` to render a clean placeholder (e.g., "No headers required") instead of omitting the section completely when a user might expect to see an invalid header.

---

### 3. Execution Engine & Variables (Week 4 Focus)

- [ ] **Execute Setup Tests Sequentially First**
  * **Requirement:** The executor must run all tests with `scenario_type: "setup"` *first*, extract their responses, populate the **Runtime Context**, and then execute the remaining tests in parallel or in sequence using the substituted variables.

- [ ] **Regex String Substitutions**
  * **Requirement:** Implement a regex-based replacement block in `executor.py` that replaces double-brace keys (like `{{USER_A_TOKEN}}`) inside request paths, query strings, headers, and JSON bodies.

---

### 4. Performance & Scale (Week 7 Focus)

- [ ] **Async Multi-Session Parallel Generation**
  * **Issue:** Sequential generation takes 8–10 seconds per endpoint.
  * **Fix:** Rework the background task to run endpoint generations concurrently using `asyncio.gather` combined with an `asyncio.Semaphore(3)` to respect rate limits, giving each coroutine its own dedicated database session.
