"""Agentic loop graph definition.

Compiles a LangGraph StateGraph with the node chain:
    execute_run -> analyze -> [decide_continue] -> generate | finalize

The checkpointer MUST be passed at compile time. It cannot be
injected later at ainvoke() time.
"""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from app.agentic.nodes import (
    analyze_node,
    decide_continue,
    execute_run_node,
    finalize_node,
    generate_node,
)
from app.agentic.state import AgenticLoopState


def build_graph(checkpointer: BaseCheckpointSaver[str] | None = None) -> Any:
    """Build and compile the agentic loop graph.

    IMPORTANT: The checkpointer MUST be passed here at compile time.
    It cannot be injected later at ainvoke() time. If no checkpointer
    is provided (e.g., in unit tests), the graph runs without persistence.
    """
    workflow = StateGraph(AgenticLoopState)

    workflow.add_node("execute_run", execute_run_node)
    workflow.add_node("analyze", analyze_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("finalize", finalize_node)

    # Use add_edge(START, ...) — set_entry_point() is deprecated in LangGraph 1.x
    workflow.add_edge(START, "execute_run")
    workflow.add_edge("execute_run", "analyze")

    workflow.add_conditional_edges(
        "analyze",
        decide_continue,
        {
            "continue": "generate",
            "finalize": "finalize",
        },
    )

    workflow.add_edge("generate", "execute_run")
    workflow.add_edge("finalize", END)

    return workflow.compile(checkpointer=checkpointer)
