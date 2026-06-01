"""Unit tests for assertion evaluation engine.

Covers all 7 assertion types plus edge cases:
  - status_eq, status_in, json_path (exists + eq), body_contains,
    body_not_contains, header_eq, response_time_lt
  - Edge: empty assertions, non-dict body with json_path, malformed jsonpath
"""


from app.runner.assertions import evaluate_assertions

# ── Shared fixtures ──────────────────────────────────────────────────────────

SAMPLE_HEADERS = {"content-type": "application/json", "x-request-id": "abc-123"}
SAMPLE_BODY = {"id": 1, "username": "admin", "email": "admin@test.com", "nested": {"key": "val"}}


# ── status_eq ────────────────────────────────────────────────────────────────

class TestStatusEq:
    def test_pass(self):
        assertions = [{"type": "status_eq", "expected": 200}]
        all_passed, results = evaluate_assertions(assertions, 200, SAMPLE_HEADERS, SAMPLE_BODY, 50)
        assert all_passed is True
        assert results[0]["passed"] is True
        assert results[0]["actual"] == 200

    def test_fail(self):
        assertions = [{"type": "status_eq", "expected": 401}]
        all_passed, results = evaluate_assertions(assertions, 200, SAMPLE_HEADERS, SAMPLE_BODY, 50)
        assert all_passed is False
        assert results[0]["passed"] is False
        assert results[0]["actual"] == 200


# ── status_in ────────────────────────────────────────────────────────────────

class TestStatusIn:
    def test_pass_in_list(self):
        assertions = [{"type": "status_in", "expected": [200, 201, 204]}]
        all_passed, results = evaluate_assertions(assertions, 201, SAMPLE_HEADERS, SAMPLE_BODY, 50)
        assert all_passed is True
        assert results[0]["passed"] is True

    def test_fail_not_in_list(self):
        assertions = [{"type": "status_in", "expected": [200, 201]}]
        all_passed, results = evaluate_assertions(assertions, 404, SAMPLE_HEADERS, SAMPLE_BODY, 50)
        assert all_passed is False

    def test_empty_list(self):
        assertions = [{"type": "status_in", "expected": []}]
        all_passed, results = evaluate_assertions(assertions, 200, SAMPLE_HEADERS, SAMPLE_BODY, 50)
        assert all_passed is False

    def test_none_expected(self):
        assertions = [{"type": "status_in"}]
        all_passed, results = evaluate_assertions(assertions, 200, SAMPLE_HEADERS, SAMPLE_BODY, 50)
        assert all_passed is False


# ── json_path ────────────────────────────────────────────────────────────────

class TestJsonPath:
    def test_exists_pass(self):
        assertions = [{"type": "json_path", "target": "$.username", "op": "exists"}]
        all_passed, results = evaluate_assertions(assertions, 200, SAMPLE_HEADERS, SAMPLE_BODY, 50)
        assert all_passed is True
        assert results[0]["actual"] == "exists"

    def test_exists_fail(self):
        assertions = [{"type": "json_path", "target": "$.nonexistent", "op": "exists"}]
        all_passed, results = evaluate_assertions(assertions, 200, SAMPLE_HEADERS, SAMPLE_BODY, 50)
        assert all_passed is False
        assert results[0]["actual"] == "not found"

    def test_eq_pass(self):
        assertions = [{"type": "json_path", "target": "$.username", "op": "eq", "expected": "admin"}]
        all_passed, results = evaluate_assertions(assertions, 200, SAMPLE_HEADERS, SAMPLE_BODY, 50)
        assert all_passed is True
        assert results[0]["actual"] == "admin"

    def test_eq_fail(self):
        assertions = [{"type": "json_path", "target": "$.username", "op": "eq", "expected": "user1"}]
        all_passed, results = evaluate_assertions(assertions, 200, SAMPLE_HEADERS, SAMPLE_BODY, 50)
        assert all_passed is False
        assert results[0]["actual"] == "admin"

    def test_nested_path(self):
        assertions = [{"type": "json_path", "target": "$.nested.key", "op": "eq", "expected": "val"}]
        all_passed, results = evaluate_assertions(assertions, 200, SAMPLE_HEADERS, SAMPLE_BODY, 50)
        assert all_passed is True

    def test_non_dict_body_errors(self):
        assertions = [{"type": "json_path", "target": "$.id", "op": "exists"}]
        all_passed, results = evaluate_assertions(assertions, 200, SAMPLE_HEADERS, "plain text body", 50)
        assert all_passed is False
        assert results[0]["error"] == "Response body is not JSON"

    def test_malformed_jsonpath(self):
        assertions = [{"type": "json_path", "target": "$[[[invalid", "op": "exists"}]
        all_passed, results = evaluate_assertions(assertions, 200, SAMPLE_HEADERS, SAMPLE_BODY, 50)
        assert all_passed is False
        assert results[0]["error"] is not None


# ── body_contains ────────────────────────────────────────────────────────────

class TestBodyContains:
    def test_pass(self):
        assertions = [{"type": "body_contains", "expected": "admin"}]
        all_passed, results = evaluate_assertions(assertions, 200, SAMPLE_HEADERS, SAMPLE_BODY, 50)
        assert all_passed is True
        assert results[0]["actual"] == "contained"

    def test_fail(self):
        assertions = [{"type": "body_contains", "expected": "nonexistent_value"}]
        all_passed, results = evaluate_assertions(assertions, 200, SAMPLE_HEADERS, SAMPLE_BODY, 50)
        assert all_passed is False
        assert results[0]["actual"] == "not contained"

    def test_string_body(self):
        assertions = [{"type": "body_contains", "expected": "hello"}]
        all_passed, results = evaluate_assertions(assertions, 200, SAMPLE_HEADERS, "hello world", 50)
        assert all_passed is True


# ── body_not_contains ────────────────────────────────────────────────────────

class TestBodyNotContains:
    def test_pass(self):
        assertions = [{"type": "body_not_contains", "expected": "secret_flag"}]
        all_passed, results = evaluate_assertions(assertions, 200, SAMPLE_HEADERS, SAMPLE_BODY, 50)
        assert all_passed is True
        assert results[0]["actual"] == "not contained"

    def test_fail_when_body_contains_value(self):
        assertions = [{"type": "body_not_contains", "expected": "admin"}]
        all_passed, results = evaluate_assertions(assertions, 200, SAMPLE_HEADERS, SAMPLE_BODY, 50)
        assert all_passed is False
        assert results[0]["actual"] == "contained"


# ── header_eq ────────────────────────────────────────────────────────────────

class TestHeaderEq:
    def test_pass(self):
        assertions = [{"type": "header_eq", "target": "content-type", "expected": "application/json"}]
        all_passed, results = evaluate_assertions(assertions, 200, SAMPLE_HEADERS, SAMPLE_BODY, 50)
        assert all_passed is True

    def test_fail(self):
        assertions = [{"type": "header_eq", "target": "content-type", "expected": "text/html"}]
        all_passed, results = evaluate_assertions(assertions, 200, SAMPLE_HEADERS, SAMPLE_BODY, 50)
        assert all_passed is False
        assert results[0]["actual"] == "application/json"

    def test_case_insensitive_header_name(self):
        assertions = [{"type": "header_eq", "target": "Content-Type", "expected": "application/json"}]
        all_passed, results = evaluate_assertions(assertions, 200, SAMPLE_HEADERS, SAMPLE_BODY, 50)
        assert all_passed is True

    def test_missing_header(self):
        assertions = [{"type": "header_eq", "target": "x-missing", "expected": "something"}]
        all_passed, results = evaluate_assertions(assertions, 200, SAMPLE_HEADERS, SAMPLE_BODY, 50)
        assert all_passed is False
        assert results[0]["actual"] is None


# ── response_time_lt ─────────────────────────────────────────────────────────

class TestResponseTimeLt:
    def test_pass(self):
        assertions = [{"type": "response_time_lt", "expected": 100}]
        all_passed, results = evaluate_assertions(assertions, 200, SAMPLE_HEADERS, SAMPLE_BODY, 50)
        assert all_passed is True
        assert results[0]["actual"] == 50

    def test_fail(self):
        assertions = [{"type": "response_time_lt", "expected": 30}]
        all_passed, results = evaluate_assertions(assertions, 200, SAMPLE_HEADERS, SAMPLE_BODY, 50)
        assert all_passed is False
        assert results[0]["actual"] == 50

    def test_exact_boundary_fails(self):
        """response_time_lt is strict less-than, so equal should fail."""
        assertions = [{"type": "response_time_lt", "expected": 50}]
        all_passed, results = evaluate_assertions(assertions, 200, SAMPLE_HEADERS, SAMPLE_BODY, 50)
        assert all_passed is False


# ── Edge cases ───────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_assertions_list(self):
        all_passed, results = evaluate_assertions([], 200, SAMPLE_HEADERS, SAMPLE_BODY, 50)
        assert all_passed is True
        assert results == []

    def test_unknown_assertion_type(self):
        assertions = [{"type": "some_unknown_type", "expected": 200}]
        all_passed, results = evaluate_assertions(assertions, 200, SAMPLE_HEADERS, SAMPLE_BODY, 50)
        assert all_passed is False
        assert results[0]["error"] == "Unknown assertion type: some_unknown_type"

    def test_multiple_assertions_mixed_results(self):
        assertions = [
            {"type": "status_eq", "expected": 200},
            {"type": "body_contains", "expected": "nonexistent"},
            {"type": "header_eq", "target": "content-type", "expected": "application/json"},
        ]
        all_passed, results = evaluate_assertions(assertions, 200, SAMPLE_HEADERS, SAMPLE_BODY, 50)
        assert all_passed is False
        assert results[0]["passed"] is True
        assert results[1]["passed"] is False
        assert results[2]["passed"] is True

    def test_all_assertions_pass(self):
        assertions = [
            {"type": "status_eq", "expected": 200},
            {"type": "body_contains", "expected": "admin"},
            {"type": "json_path", "target": "$.id", "op": "eq", "expected": 1},
        ]
        all_passed, results = evaluate_assertions(assertions, 200, SAMPLE_HEADERS, SAMPLE_BODY, 50)
        assert all_passed is True
        assert all(r["passed"] for r in results)
