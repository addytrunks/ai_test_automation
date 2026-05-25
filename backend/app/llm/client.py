"""
LiteLLM wrapper for structured output generation.

Uses litellm.acompletion with a Pydantic model as response_format
to get structured JSON from any supported LLM provider.
"""

from __future__ import annotations

import logging
from typing import TypeVar

import litellm
from pydantic import BaseModel

from app.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


async def generate_structured(
    prompt: str,
    response_model: type[T],
    system_prompt: str = "You are a helpful assistant.",
    temperature: float = 0.1,
) -> T:
    """
    Call the LLM specified in config and return a structured Pydantic object.

    Uses litellm to abstract the provider. The response_format parameter
    tells litellm to enforce structured JSON output matching the Pydantic model.
    """
    settings = get_settings()

    # Configure litellm api key based on provider prefix
    if settings.llm_model.startswith("openai/"):
        litellm.api_key = settings.openai_api_key
    elif settings.llm_model.startswith("openrouter/"):
        litellm.api_key = settings.openrouter_api_key

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    try:
        # We are using acompletion instead of completion (sync call) - to avoid blocking because the user is using an async function.
        response = await litellm.acompletion(
            model=settings.llm_model,
            messages=messages,
            response_format=response_model,
            temperature=temperature,
        )
        content = response.choices[0].message.content
        return response_model.model_validate_json(content)
    except Exception as e:
        logger.exception("LLM generation failed for model=%s", settings.llm_model)
        raise RuntimeError(f"LLM generation failed: {e}") from e
