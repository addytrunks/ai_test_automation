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


def _endpoint_requires_auth(endpoint_dict: dict[str, Any]) -> bool:
    """Return True if the endpoint has a non-empty security requirement."""
    security = endpoint_dict.get("security")
    if security:
        return True
    # Also check if any parameter is named 'Authorization' (fallback heuristic)
    for param in endpoint_dict.get("parameters") or []:
        if isinstance(param, dict) and param.get("name", "").lower() == "authorization":
            return True
    return False


def build_generation_prompt(endpoint_dict: dict[str, Any], scenarios: list[str]) -> str:
    """
    Assemble a full prompt for test generation.

    Structure: few-shot examples FIRST (so the model infers the pattern),
    then the task-specific endpoint details and instructions.

    If the endpoint requires authentication and 'setup' is not already in the
    requested scenarios, setup examples are prepended automatically so the model
    knows to emit token-acquisition tests before auth-dependent tests.
    """
    # Auto-inject setup scenario when endpoint requires auth
    effective_scenarios = list(scenarios)
    if _endpoint_requires_auth(endpoint_dict) and "setup" not in effective_scenarios:
        effective_scenarios = ["setup"] + effective_scenarios

    endpoint_json = json.dumps(endpoint_dict, indent=2, default=str)
    patterns = load_patterns(effective_scenarios)

    # Few-shot examples come first so the model sees the pattern before the task
    prompt = "Use the following examples to understand the expected test case format:\n"
    prompt += patterns + "\n"
    prompt += "---\n"
    prompt += "Now generate test cases for this API endpoint:\n\n"
    prompt += f"Endpoint details:\n{endpoint_json}\n\n"
    prompt += f"Requested scenario types: {', '.join(effective_scenarios)}\n\n"
    prompt += "Instructions:\n"
    prompt += "- Generate at least 2 tests per scenario type.\n"
    prompt += "- path_params keys must exactly match the template variables in the path (e.g. {id} → key 'id').\n"
    prompt += "- Include appropriate headers (like Content-Type: application/json).\n"
    prompt += "- Include at least one 'status_eq' or 'status_in' assertion per test.\n"
    prompt += "- For security tests (injection, bola, mass_assignment), include "
    prompt += "'body_not_contains' assertions to detect reflected payloads.\n"
    prompt += "- NEVER use hardcoded token strings or UUID placeholders. "
    prompt += "Use ONLY these template variables: {{USER_A_TOKEN}}, {{USER_B_TOKEN}}, "
    prompt += "{{ADMIN_TOKEN}}, {{USER_A_ID}}, {{USER_B_ID}}, {{TARGET_RESOURCE_ID}}.\n"
    prompt += "- If the endpoint requires authentication, emit setup tests first "
    prompt += "with an 'extract' field that captures tokens from the login response.\n"

    return prompt