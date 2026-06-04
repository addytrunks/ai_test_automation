"""LangGraph checkpointer factory.

Provides the AsyncPostgresSaver context manager using the
psycopg3-compatible CHECKPOINTER_URL from settings.
The checkpointer MUST be obtained before calling build_graph()
and passed at compile time — it cannot be injected at ainvoke().
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.config import get_settings


@asynccontextmanager
async def get_checkpointer() -> AsyncGenerator[AsyncPostgresSaver, None]:
    """Yield an initialized async Postgres checkpointer.

    Uses the CHECKPOINTER_URL from settings (must be postgresql:// scheme).
    Calls setup() on first use to create checkpoint tables (idempotent).
    """
    settings = get_settings()
    if not settings.checkpointer_url:
        raise RuntimeError(
            "CHECKPOINTER_URL is not set. The agentic loop requires a "
            "psycopg3-compatible connection string (postgresql:// scheme)."
        )
    async with AsyncPostgresSaver.from_conn_string(settings.checkpointer_url) as saver:
        await saver.setup()
        yield saver
