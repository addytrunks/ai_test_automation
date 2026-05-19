import pytest
from sqlalchemy import text

from app.db import Base, get_engine, get_sessionmaker


@pytest.mark.asyncio
async def test_engine_can_execute_select_one(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("JWT_SECRET", "x")
    # clear cached settings
    from app.config import get_settings

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()

    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar_one() == 1
    await engine.dispose()


@pytest.mark.asyncio
async def test_sessionmaker_yields_session(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("JWT_SECRET", "x")
    from app.config import get_settings

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()

    SessionLocal = get_sessionmaker()
    async with SessionLocal() as session:
        result = await session.execute(text("SELECT 2"))
        assert result.scalar_one() == 2


def test_base_is_declarative_base():
    assert hasattr(Base, "metadata")
