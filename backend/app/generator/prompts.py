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
                )
                anti = content.get("anti_patterns")
                if anti:
                    patterns_text += "Anti-patterns (do NOT generate these):\n"
                    for item in anti:
                        patterns_text += f"  - {item}\n"
                patterns_text += (
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
    *,
    include_auth_context: bool = False,
    gap_mode: bool = False,
    gap_description: str | None = None,
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

    prompt = "Use the following examples to understand the expected test case format:\n"
    prompt += patterns + "\n"
    prompt += "---\n"
    prompt += "Now generate test cases for this API endpoint:\n\n"
    prompt += f"Endpoint details:\n{endpoint_json}\n\n"

    inject_auth = auth_endpoint_dict and (include_setup or include_auth_context)
    if inject_auth:
        auth_json = json.dumps(auth_endpoint_dict, indent=2, default=str)
        prompt += (
            "Authentication (Login) Endpoint details "
            "(use for setup tests and to determine token field names in responses):\n"
            f"{auth_json}\n\n"
        )
    if register_endpoint_dict and (include_setup or include_auth_context):
        reg_json = json.dumps(register_endpoint_dict, indent=2, default=str)
        prompt += (
            "Registration Endpoint details "
            "(use to generate register setup tests BEFORE login when setup is requested):\n"
            f"{reg_json}\n\n"
        )

    prompt += f"Requested scenario types: {', '.join(effective_scenarios)}\n\n"
    prompt += "Instructions:\n"
    prompt += (
        "- STRICT CONSTRAINT: ONLY generate tests for the scenario types listed above. "
        "Do not add unrequested scenario types.\n"
    )
    if gap_mode:
        prompt += (
            "- Generate 1–2 highly targeted tests for the coverage gap described below. "
            "Quality over quantity.\n"
        )
        if gap_description:
            prompt += f"- Coverage gap to address: {gap_description}\n"
    else:
        prompt += (
            "- Generate 1–3 tests per requested scenario type. Prefer distinct attack vectors "
            "over duplicates. For setup, generate only what is needed (register + login per user).\n"
        )
    prompt += "- path_params keys must exactly match path template variables (e.g. {username} → 'username').\n"
    prompt += "- Include Content-Type: application/json for JSON request bodies.\n"
    prompt += "- Include at least one status_eq or status_in assertion per test.\n"
    prompt += (
        "- Prefer status assertions. Use body_contains/body_not_contains only when the OpenAPI "
        "spec documents response fields or to detect payload reflection you sent.\n"
    )
    prompt += (
        "- Use template variables for tokens and dynamic IDs. "
        "Authorization: \"Bearer {{USER_A_TOKEN}}\" (include Bearer prefix).\n"
    )
    if include_setup:
        prompt += (
            "- Emit setup tests first. Setup tests use the auth/register endpoints' method and path, "
            "not the target endpoint.\n"
            "- Setup tests MUST include a JSON request body ('body') that fully complies with the required "
            "requestBody properties of the registration and login endpoints (e.g., matching required fields like 'email', 'password', 'full_name'). "
            "Do NOT use template variables inside setup request bodies; use realistic dummy data.\n"
            "- Login setup tests MUST include the 'extract' mapping to extract credentials from the response. "
            "Read the token field name from the login endpoint's response schema (e.g., extracting 'access_token' via '$.access_token' into 'USER_A_TOKEN' / 'USER_B_TOKEN').\n"
            "- Registration setup tests MUST include the 'static_context' mapping for user identifiers (e.g., {'USER_A_ID': 'user_a_email'} / {'USER_B_ID': 'user_b_email'}).\n"
        )
        if register_endpoint_dict:
            prompt += (
                "- CRITICAL: A registration endpoint is provided above. You MUST generate register "
                "setup tests for each user (User A, User B) BEFORE their login setup tests. "
                "Without registration, login will fail because the users do not exist yet.\n"
            )
    elif include_auth_context:
        prompt += (
            "- Setup tests already exist in this suite. Use {{USER_A_TOKEN}} / {{USER_B_TOKEN}} "
            "in headers — do NOT generate new setup tests.\n"
        )

    return prompt
