from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield


def create_app() -> FastAPI:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s:\t  %(message)s",
    )
    
    settings = get_settings()
    app = FastAPI(
        title="AI-Assisted API Test Generation Platform",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/v1/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # Auth router
    from app.auth.router import router as auth_router

    app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])

    # Specs router
    from app.specs.router import router as specs_router

    app.include_router(specs_router, prefix="/api/v1", tags=["specs"])

    # Generator router
    from app.generator.router import router as generator_router

    app.include_router(generator_router, prefix="/api/v1", tags=["generator"])

    # Runner router
    from app.runner.router import router as runner_router

    app.include_router(runner_router, prefix="/api/v1", tags=["runner"])

    # Analyzer router
    from app.analyzer.router import router as analyzer_router

    app.include_router(analyzer_router, prefix="/api/v1", tags=["analyzer"])

    return app


app = create_app()
