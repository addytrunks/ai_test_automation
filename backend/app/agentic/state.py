"""Agentic loop state definition.

Defines the TypedDict that flows through the LangGraph StateGraph.
Every node reads from and writes partial updates back to this state.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict


class AgenticLoopState(TypedDict):
    """State carried through each iteration of the agentic loop.

    Attributes:
        test_suite_id: UUID of the test suite being evaluated.
        target_base_url: Base URL of the target API (e.g. http://localhost:5001).
        current_depth: Number of loop iterations completed so far.
        max_depth: Hard cap on loop iterations (clamped to 5 by guards).
        max_tests_per_cycle: Max tests the generate_node may create per iteration.
        last_run_id: UUID of the most recent Run created by execute_run_node.
        last_gaps: Serialized list of coverage gaps from the latest analysis.
        new_test_ids: UUIDs of tests generated in this iteration only.
            CRITICAL: On depth > 0, execute_run_node runs ONLY these tests
            to avoid redundantly re-running the entire suite.
        total_tokens_used: Cumulative LLM token spend across all iterations.
            Uses operator.add reducer so nodes return only their own spend
            and LangGraph handles accumulation. Safe for parallel branches.
        final_status: Set by finalize_node when the loop terminates.
    """

    test_suite_id: str
    target_base_url: str
    current_depth: int
    max_depth: int
    max_tests_per_cycle: int
    last_run_id: str | None
    last_gaps: list[dict[str, Any]]
    new_test_ids: list[str]
    total_tokens_used: Annotated[int, operator.add]
    final_status: Literal["completed", "max_depth_hit", "no_high_gaps", "token_budget_hit", "error"] | None
