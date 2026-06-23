"""Smoke-test LLM test generation with refined prompts.

Fetches VAmPI OpenAPI (or uses a built-in fallback), generates auth_bypass
tests for a secured endpoint, and validates prompt compliance.
"""

from __future__ import annotations

import asyncio
import json
import sys

import httpx

from app.generator.prompts import build_generation_prompt
from app.generator.schemas import TestListResult
from app.generator.service import SYSTEM_PROMPT
from app.llm.client import generate_structured


VAMPI_OPENAPI_URLS = [
    "http://localhost:5001/openapi.json",
    "http://localhost:5001/apispec_1.json",
    "http://localhost:5001/swagger.json",
]

FALLBACK_ENDPOINT = {
    "method": "GET",
    "path": "/users/v1/{username}",
    "summary": "Get user by username",
    "parameters": [
        {"name": "username", "in": "path", "required": True, "schema": {"type": "string"}},
    ],
    "request_body": None,
    "responses": {"200": {"description": "OK"}, "401": {"description": "Unauthorized"}},
    "security": [{"bearerAuth": []}],
}

FALLBACK_AUTH = {
    "method": "POST",
    "path": "/users/v1/login",
    "summary": "Login",
    "parameters": [],
    "request_body": {
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {"username": {"type": "string"}, "password": {"type": "string"}},
                }
            }
        }
    },
    "responses": {
        "200": {
            "description": "OK",
            "content": {"application/json": {"schema": {"properties": {"auth_token": {"type": "string"}}}}},
        }
    },
}


async def _fetch_vampi_spec() -> dict | None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        for url in VAMPI_OPENAPI_URLS:
            try:
                r = await client.get(url)
                if r.status_code == 200:
                    print(f"Loaded OpenAPI from {url}")
                    return r.json()
            except Exception:
                continue
    return None


def _find_endpoint(spec: dict, path: str, method: str) -> dict | None:
    paths = spec.get("paths", {})
    item = paths.get(path, {}).get(method.lower())
    if not item:
        return None
    return {
        "method": method.upper(),
        "path": path,
        "summary": item.get("summary"),
        "parameters": item.get("parameters"),
        "request_body": item.get("requestBody"),
        "responses": item.get("responses"),
        "security": item.get("security", spec.get("security")),
    }


async def main() -> int:
    spec = await _fetch_vampi_spec()
    if spec:
        endpoint = _find_endpoint(spec, "/users/v1/{username}", "get") or FALLBACK_ENDPOINT
        auth_ep = _find_endpoint(spec, "/users/v1/login", "post") or FALLBACK_AUTH
    else:
        print("VAmPI not reachable — using fallback endpoint definitions")
        endpoint = FALLBACK_ENDPOINT
        auth_ep = FALLBACK_AUTH

    scenarios = ["auth_bypass"]
    prompt = build_generation_prompt(
        endpoint,
        scenarios,
        auth_endpoint_dict=auth_ep,
        include_auth_context=True,
    )

    print(f"\nPrompt length: {len(prompt)} chars")
    print("Calling LLM for auth_bypass tests...\n")

    result = await generate_structured(
        prompt=prompt,
        response_model=TestListResult,
        system_prompt=SYSTEM_PROMPT,
        temperature=0.4,
    )

    print(f"Generated {len(result.tests)} tests:\n")
    checks = {
        "has_missing_auth_test": False,
        "has_invalid_token_with_header": False,
        "all_have_status_assertion": True,
    }

    for t in result.tests:
        print(f"  [{t.scenario_type}] {t.name}")
        print(f"    headers: {json.dumps(t.headers)}")
        print(f"    assertions: {[a.type for a in t.assertions]}")
        auth_hdr = (t.headers or {}).get("Authorization", "")
        if not t.headers or "Authorization" not in (t.headers or {}):
            checks["has_missing_auth_test"] = True
        if auth_hdr and "invalid" in str(auth_hdr).lower():
            checks["has_invalid_token_with_header"] = True
        if not any(a.type in ("status_eq", "status_in") for a in t.assertions):
            checks["all_have_status_assertion"] = False

    print("\nCompliance checks:")
    for k, v in checks.items():
        status = "PASS" if v else "FAIL"
        print(f"  {k}: {status}")

    ok = (
        len(result.tests) >= 1
        and checks["all_have_status_assertion"]
        and (checks["has_missing_auth_test"] or checks["has_invalid_token_with_header"])
    )
    if ok:
        print("\nGeneration verification: SUCCESS")
        return 0
    print("\nGeneration verification: NEEDS REVIEW (see checks above)")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
