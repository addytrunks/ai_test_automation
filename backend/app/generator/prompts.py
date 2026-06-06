"""
Prompt construction for LLM-driven test generation.

Reads few-shot pattern files from the patterns/ directory and assembles
them with endpoint details into a comprehensive prompt.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import yaml

logger = logging.getLogger(__name__)


def load_patterns(scenarios: list[str]) -> str:
    """Load few-shot YAML patterns for the requested scenario types.

    Logs a warning if a pattern file is missing for a requested scenario.
    """
    patterns_text = ""
    base_dir = os.path.dirname(__file__)
    for scenario in scenarios:
        path = os.path.join(base_dir, "patterns", f"{scenario}.yaml")
        if os.path.exists(path):
            with open(path) as f:
                content = yaml.safe_load(f)
                patterns_text += (
                    f"\nScenario Type: {scenario}\n"
                    f"Description: {content.get('description', '')}\n"
                    f"Examples:\n{yaml.dump(content.get('examples', []), default_flow_style=False)}\n"
                )
        else:
            logger.warning(
                "Pattern file not found for scenario '%s' at %s — "
                "the model will receive no few-shot examples for this scenario type",
                scenario,
                path,
            )
    return patterns_text


def build_generation_prompt(
    endpoint_dict: dict[str, Any],
    scenarios: list[str],
    auth_endpoint_dict: dict[str, Any] | None = None,
    register_endpoint_dict: dict[str, Any] | None = None,
    include_setup: bool = False,
) -> str:
    """
    Builds the complete prompt string to send to the LLM.

    Structure: few-shot examples FIRST (so the model infers the pattern),
    then the task-specific endpoint details and instructions.
    """
    effective_scenarios = list(scenarios)
    if include_setup and "setup" not in effective_scenarios:
        effective_scenarios = ["setup"] + effective_scenarios

    endpoint_json = json.dumps(endpoint_dict, indent=2, default=str)
    patterns = load_patterns(effective_scenarios)

    # Few-shot examples come first so the model sees the pattern before the task
    prompt = "Use the following examples to understand the expected test case format:\n"
    prompt += patterns + "\n"
    prompt += "---\n"
    prompt += "Now generate test cases for this API endpoint:\n\n"
    prompt += f"Endpoint details:\n{endpoint_json}\n\n"
    if auth_endpoint_dict and "setup" in effective_scenarios:
        auth_json = json.dumps(auth_endpoint_dict, indent=2, default=str)
        prompt += f"Authentication (Login) Endpoint details (use this to generate login setup tests):\n{auth_json}\n\n"
    if register_endpoint_dict and "setup" in effective_scenarios:
        reg_json = json.dumps(register_endpoint_dict, indent=2, default=str)
        prompt += f"Registration Endpoint details (use this to generate register setup tests BEFORE login):\n{reg_json}\n\n"
        
    prompt += f"Requested scenario types: {', '.join(effective_scenarios)}\n\n"
    prompt += "Instructions:\n"
    prompt += "- STRICT CONSTRAINT: ONLY generate test cases for the scenario types listed under 'Requested scenario types' above. Do NOT generate test cases for positive, negative, boundary, or any other scenario type unless it is explicitly requested above.\n"
    prompt += "- Generate at least 2 tests per scenario type (NOTE:except for 'setup', where you should generate exactly what is needed without duplication).\n"
    prompt += "- path_params keys must exactly match the template variables in the path (e.g. {id} → key 'id').\n"
    prompt += "- Include appropriate headers (like Content-Type: application/json).\n"
    prompt += "- Include at least one 'status_eq' or 'status_in' assertion per test.\n"
    prompt += "- ASSERTION CONSTRAINT: Only generate assertions that can be verified against the OpenAPI spec. Status code assertions are always valid. For 'body_contains' and 'body_not_contains', only assert on values explicitly defined in the spec's response schema, or on payloads you sent in the request (e.g. checking an injection payload wasn't reflected). Never assert on exact error message text unless the spec documents it. For negative and boundary tests, 'status_eq' alone is sufficient unless the spec explicitly defines the error response body.\n"
    prompt += "- NEVER use hardcoded token strings or UUID placeholders. "
    prompt += "Use ONLY these template variables: {{USER_A_TOKEN}}, {{USER_B_TOKEN}}, "
    prompt += "{{USER_A_ID}}, {{USER_B_ID}}, {{TARGET_RESOURCE_ID}}.\n"
    if "setup" in effective_scenarios:
        prompt += "- If the endpoint requires authentication, emit setup tests first. "
        prompt += "Setup tests MUST include 'method' and 'path' fields pointing to the actual "
        prompt += "auth endpoint (e.g. POST /users/v1/login), NOT the target endpoint.\n"
        prompt += "- If a registration endpoint exists, generate a Register setup test BEFORE "
        prompt += "the Login setup test. Never assume users already exist.\n"
        prompt += "- Login setup tests must have an 'extract' field that captures tokens from the response.\n"

    return prompt