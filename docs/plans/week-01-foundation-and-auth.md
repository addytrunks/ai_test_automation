# Week 1 Implementation Plan — Foundation & Auth

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a working FastAPI + React + Postgres skeleton with JWT-based auth so that by end of week a user can register, login, and reach a protected dashboard placeholder.

**Architecture:** Modular monolith (FastAPI). Async SQLAlchemy + Alembic for migrations. Bcrypt password hashing, JWT (HS256) via `python-jose`. React 18 + Vite + Tailwind + shadcn/ui frontend; Zustand for auth state; TanStack Query for server state. Postgres + VAmPI as docker-compose services for dev; backend/frontend run locally for fast iteration.

**Tech Stack:** Python 3.11, FastAPI 0.128, SQLAlchemy 2.0 (async), Alembic 1.13, Pydantic 2.9, passlib[bcrypt], python-jose, ruff, mypy, pytest + pytest-asyncio, React 18, Vite 7, TypeScript 5, Tailwind, shadcn/ui, Zustand, TanStack Query 5, axios.

**Verification gate:** `docker compose up` brings up Postgres + VAmPI; running backend and frontend locally lets you register a new account, log in, and land on `/dashboard` with the user's email shown. Logout returns to `/login`. Refreshing the dashboard preserves auth. CI passes ruff + mypy + pytest.

---

## File Structure for Week 1

**Backend (`backend/`):**
- `pyproject.toml` — deps, ruff/mypy/pytest config
- `.env.example` — all env vars with sane defaults
- `alembic.ini`, `alembic/env.py`, `alembic/versions/` — migration setup
- `app/__init__.py` — package marker
- `app/main.py` — FastAPI app, CORS, router registration, lifespan
- `app/config.py` — pydantic-settings, reads env
- `app/db.py` — async engine + session factory
- `app/models.py` — `User` model only this week
- `app/schemas.py` — `UserCreate`, `UserRead`, `TokenResponse`
- `app/deps.py` — `get_db`, `get_current_user` deps
- `app/auth/__init__.py`
- `app/auth/service.py` — password hashing, JWT issue/verify, user CRUD
- `app/auth/router.py` — `/auth/register`, `/auth/login`, `/auth/me`
- `tests/conftest.py` — pytest fixtures (test DB, client)
- `tests/test_auth.py` — register, login, me, invalid token

**Frontend (`frontend/`):**
- `package.json`, `tsconfig.json`, `vite.config.ts`, `tailwind.config.js`, `postcss.config.js`
- `index.html`
- `src/main.tsx`, `src/App.tsx`, `src/index.css`
- `src/api/client.ts` — axios with bearer interceptor
- `src/api/auth.ts` — register/login/me functions
- `src/hooks/useAuthStore.ts` — Zustand store for token + user
- `src/components/ProtectedRoute.tsx`
- `src/components/ui/` — shadcn primitives (button, input, card, label, form)
- `src/pages/Login.tsx`, `src/pages/Register.tsx`, `src/pages/Dashboard.tsx`

**Repo root:**
- `docker-compose.yml` — Postgres 16 + VAmPI
- `.env.example`
- `.gitignore`
- `.github/workflows/ci.yml`
- `README.md`
- `docs/adr/001-modular-monolith.md`

---

## Task 1: Initialize repo + Git + ignore files

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\.gitignore`
- Create: `C:\AI_TEST_AUTOMATION\README.md`
- Create: `C:\AI_TEST_AUTOMATION\.env.example`

- [ ] **Step 1: Initialize git repo (skip if already initialized)**

Run from `C:\AI_TEST_AUTOMATION\`:
```bash
git init
git branch -M main
```

- [ ] **Step 2: Create `.gitignore`**

Write `C:\AI_TEST_AUTOMATION\.gitignore`:
```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
.env
.env.local
*.db
*.sqlite

# Node
node_modules/
dist/
.vite/

# IDE
.idea/
.vscode/
*.swp

# OS
.DS_Store
Thumbs.db

# Project
backend/dev.db
backend/.pytest_cache/
backend/.mypy_cache/
backend/.ruff_cache/
backend/htmlcov/
backend/.coverage
```

- [ ] **Step 3: Create root `.env.example`**

Write `C:\AI_TEST_AUTOMATION\.env.example`:
```bash
# Backend
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/apitest
JWT_SECRET=change-me-to-a-long-random-string
JWT_ALGORITHM=HS256
JWT_EXPIRES_MINUTES=1440
CORS_ORIGINS=http://localhost:5173

# LLM (used from Week 3; harmless to set now)
LLM_MODEL=openai/gpt-4o-mini
OPENAI_API_KEY=sk-replace-me

# VAmPI demo target (used from Week 4)
VAMPI_BASE_URL=http://localhost:5001
```

- [ ] **Step 4: Create README.md skeleton**

Write `C:\AI_TEST_AUTOMATION\README.md`:
```markdown
# AI-Assisted API Test Generation Platform

Internship project — production-style POC for generating, executing, and
agentically iterating on API test suites.

See `docs/specs/2026-05-14-api-test-platform-design.md` for the full design.

## Quickstart (dev)

```bash
# 1. Bring up Postgres + VAmPI
docker compose up -d

# 2. Backend
cd backend
python -m venv .venv && source .venv/Scripts/activate  # Windows bash
pip install -e .
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# 3. Frontend (new shell)
cd frontend
npm install
npm run dev
```

Then open http://localhost:5173.
```

- [ ] **Step 5: Commit**

```bash
git add .gitignore README.md .env.example
git commit -m "chore: initialize repo with gitignore, readme, env template"
```

---

## Task 2: docker-compose for Postgres + VAmPI

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\docker-compose.yml`

- [ ] **Step 1: Write docker-compose.yml**

Write `C:\AI_TEST_AUTOMATION\docker-compose.yml`:
```yaml
services:
  postgres:
    image: postgres:16-alpine
    container_name: apitest-postgres
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: apitest
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d apitest"]
      interval: 5s
      timeout: 3s
      retries: 5

  vampi:
    image: erev0s/vampi:latest
    container_name: apitest-vampi
    environment:
      vulnerable: "1"
    ports:
      - "5001:5000"
    restart: unless-stopped

volumes:
  postgres_data:
```

- [ ] **Step 2: Bring it up to verify**

```bash
docker compose up -d
docker compose ps
```

Expected: both `apitest-postgres` and `apitest-vampi` show `running`/`healthy`. VAmPI listens on `http://localhost:5001`.

- [ ] **Step 3: Smoke test VAmPI**

```bash
curl http://localhost:5001/
```

Expected: a small JSON or HTML body (VAmPI's index). If the call fails, check `docker compose logs vampi`.

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml
git commit -m "feat(infra): add docker-compose with Postgres and VAmPI"
```

---

## Task 3: Backend pyproject.toml + tooling config

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\backend\pyproject.toml`
- Create: `C:\AI_TEST_AUTOMATION\backend\.env.example`

- [ ] **Step 1: Create `backend/pyproject.toml`**

Write `C:\AI_TEST_AUTOMATION\backend\pyproject.toml`:
```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "apitest-backend"
version = "0.1.0"
description = "AI-Assisted API Test Generation Platform — backend"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.128,<0.129",
    "uvicorn[standard]>=0.30",
    "sqlalchemy[asyncio]>=2.0,<3",
    "alembic>=1.13",
    "asyncpg>=0.29",
    "aiosqlite>=0.20",
    "pydantic>=2.9,<3",
    "pydantic-settings>=2.6",
    "python-jose[cryptography]>=3.3",
    "passlib[bcrypt]>=1.7.4",
    "python-multipart>=0.0.9",
    "httpx>=0.27,<0.28",
    "structlog>=24",
]

[project.optional-dependencies]
dev = [
    "ruff>=0.6",
    "mypy>=1.11",
    "pytest>=8",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5",
    "httpx>=0.27",
]

[tool.setuptools.packages.find]
where = ["."]
include = ["app*"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "ASYNC", "SIM"]
ignore = ["E501"]  # handled by formatter

[tool.mypy]
python_version = "3.11"
strict = true
plugins = ["pydantic.mypy"]
exclude = ["alembic/"]

[[tool.mypy.overrides]]
module = ["jose.*", "passlib.*"]
ignore_missing_imports = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 2: Create `backend/.env.example`**

Write `C:\AI_TEST_AUTOMATION\backend\.env.example`:
```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/apitest
JWT_SECRET=change-me-to-a-long-random-string
JWT_ALGORITHM=HS256
JWT_EXPIRES_MINUTES=1440
CORS_ORIGINS=http://localhost:5173
LLM_MODEL=openai/gpt-4o-mini
OPENAI_API_KEY=sk-replace-me
VAMPI_BASE_URL=http://localhost:5001
```

- [ ] **Step 3: Create venv and install**

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate    # Windows bash
pip install --upgrade pip
pip install -e ".[dev]"
```

Expected: completes without errors, no version conflicts.

- [ ] **Step 4: Smoke test tooling**

```bash
ruff --version
mypy --version
pytest --version
```

All three should print version numbers.

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml backend/.env.example
git commit -m "chore(backend): add pyproject with deps and tool config"
```

---

## Task 4: Backend config module

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\backend\app\__init__.py`
- Create: `C:\AI_TEST_AUTOMATION\backend\app\config.py`
- Create: `C:\AI_TEST_AUTOMATION\backend\tests\__init__.py`
- Create: `C:\AI_TEST_AUTOMATION\backend\tests\test_config.py`

- [ ] **Step 1: Write the failing test**

Write `C:\AI_TEST_AUTOMATION\backend\tests\test_config.py`:
```python
from app.config import Settings


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_EXPIRES_MINUTES", "60")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-4o-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("VAMPI_BASE_URL", "http://localhost:5001")

    s = Settings()

    assert s.database_url == "sqlite+aiosqlite:///:memory:"
    assert s.jwt_secret == "test-secret"
    assert s.jwt_expires_minutes == 60
    assert s.cors_origins == ["http://localhost:5173", "http://127.0.0.1:5173"]
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd backend
pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.config'`.

- [ ] **Step 3: Create `app/__init__.py` and `tests/__init__.py`**

Write empty files:
- `C:\AI_TEST_AUTOMATION\backend\app\__init__.py`
- `C:\AI_TEST_AUTOMATION\backend\tests\__init__.py`

- [ ] **Step 4: Implement `app/config.py`**

Write `C:\AI_TEST_AUTOMATION\backend\app\config.py`:
```python
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = Field(...)
    jwt_secret: str = Field(...)
    jwt_algorithm: str = Field("HS256")
    jwt_expires_minutes: int = Field(1440)
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    llm_model: str = Field("openai/gpt-4o-mini")
    openai_api_key: str = Field("")
    vampi_base_url: str = Field("http://localhost:5001")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
```

- [ ] **Step 5: Run test, verify it passes**

```bash
pytest tests/test_config.py -v
```

Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/__init__.py backend/app/config.py backend/tests/__init__.py backend/tests/test_config.py
git commit -m "feat(config): add Settings with pydantic-settings"
```

---

## Task 5: Async SQLAlchemy engine + session

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\backend\app\db.py`
- Create: `C:\AI_TEST_AUTOMATION\backend\tests\test_db.py`

- [ ] **Step 1: Write the failing test**

Write `C:\AI_TEST_AUTOMATION\backend\tests\test_db.py`:
```python
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

    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar_one() == 1


@pytest.mark.asyncio
async def test_sessionmaker_yields_session(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("JWT_SECRET", "x")
    from app.config import get_settings
    get_settings.cache_clear()

    SessionLocal = get_sessionmaker()
    async with SessionLocal() as session:
        result = await session.execute(text("SELECT 2"))
        assert result.scalar_one() == 2


def test_base_is_declarative_base():
    assert hasattr(Base, "metadata")
```

- [ ] **Step 2: Run test, verify it fails**

```bash
pytest tests/test_db.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.db'`.

- [ ] **Step 3: Implement `app/db.py`**

Write `C:\AI_TEST_AUTOMATION\backend\app\db.py`:
```python
from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=False,
        future=True,
    )


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=get_engine(),
        expire_on_commit=False,
        autoflush=False,
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    SessionLocal = get_sessionmaker()
    async with SessionLocal() as session:
        yield session
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
pytest tests/test_db.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/db.py backend/tests/test_db.py
git commit -m "feat(db): add async engine, sessionmaker, and Base declarative"
```

---

## Task 6: User model + Alembic setup + first migration

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\backend\app\models.py`
- Create: `C:\AI_TEST_AUTOMATION\backend\alembic.ini`
- Create: `C:\AI_TEST_AUTOMATION\backend\alembic\env.py`
- Create: `C:\AI_TEST_AUTOMATION\backend\alembic\script.py.mako`
- Create: `C:\AI_TEST_AUTOMATION\backend\alembic\versions\.gitkeep`

- [ ] **Step 1: Write User model**

Write `C:\AI_TEST_AUTOMATION\backend\app\models.py`:
```python
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
```

- [ ] **Step 2: Initialize Alembic**

```bash
cd backend
alembic init -t async alembic
```

This creates `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/`.

- [ ] **Step 3: Edit `alembic.ini`**

In `C:\AI_TEST_AUTOMATION\backend\alembic.ini`, find the `sqlalchemy.url = ...` line and **remove it entirely** (we set URL from code).

Find the `[loggers]`-related sections and leave defaults.

- [ ] **Step 4: Edit `alembic/env.py`**

Replace the entire contents of `C:\AI_TEST_AUTOMATION\backend\alembic\env.py` with:
```python
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.config import get_settings
from app.db import Base
from app import models  # noqa: F401  (import for autogenerate)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    return get_settings().database_url


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 5: Add `.gitkeep` to versions directory**

Create empty file `C:\AI_TEST_AUTOMATION\backend\alembic\versions\.gitkeep`.

- [ ] **Step 6: Make sure docker Postgres is up + create `.env`**

```bash
docker compose up -d postgres
cd backend
cp .env.example .env
```

Edit `backend/.env` and set `JWT_SECRET` to any non-empty value.

- [ ] **Step 7: Generate the first migration**

```bash
cd backend
alembic revision --autogenerate -m "create users table"
```

Expected: a new file in `alembic/versions/` with the User table create.

- [ ] **Step 8: Apply the migration**

```bash
alembic upgrade head
```

Expected: `INFO [alembic.runtime.migration] Running upgrade -> <revision>, create users table`.

Verify in psql:
```bash
docker exec -it apitest-postgres psql -U postgres -d apitest -c "\d users"
```

Expected: shows the `users` table with columns `id`, `email`, `password_hash`, `name`, `created_at`, `updated_at`.

- [ ] **Step 9: Commit**

```bash
git add backend/app/models.py backend/alembic.ini backend/alembic/env.py backend/alembic/script.py.mako backend/alembic/versions/
git commit -m "feat(db): add User model and initial migration via Alembic"
```

---

## Task 7: Pydantic schemas for auth

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\backend\app\schemas.py`
- Create: `C:\AI_TEST_AUTOMATION\backend\tests\test_schemas.py`

- [ ] **Step 1: Write failing test**

Write `C:\AI_TEST_AUTOMATION\backend\tests\test_schemas.py`:
```python
import pytest
from pydantic import ValidationError

from app.schemas import TokenResponse, UserCreate, UserLogin, UserRead


def test_user_create_requires_email_and_password():
    u = UserCreate(email="a@b.com", password="hunter2hunter2", name="A B")
    assert u.email == "a@b.com"
    assert u.password == "hunter2hunter2"


def test_user_create_rejects_short_password():
    with pytest.raises(ValidationError):
        UserCreate(email="a@b.com", password="short")


def test_user_create_rejects_bad_email():
    with pytest.raises(ValidationError):
        UserCreate(email="not-an-email", password="hunter2hunter2")


def test_user_login_minimal_fields():
    u = UserLogin(email="a@b.com", password="hunter2hunter2")
    assert u.email == "a@b.com"


def test_user_read_excludes_password():
    import uuid
    from datetime import datetime, timezone
    payload = {
        "id": uuid.uuid4(),
        "email": "a@b.com",
        "name": "A B",
        "created_at": datetime.now(timezone.utc),
    }
    u = UserRead(**payload)
    assert "password" not in u.model_dump()


def test_token_response_shape():
    t = TokenResponse(access_token="abc", token_type="bearer")
    d = t.model_dump()
    assert d == {"access_token": "abc", "token_type": "bearer"}
```

- [ ] **Step 2: Run test, verify it fails**

```bash
pytest tests/test_schemas.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `app/schemas.py`**

Write `C:\AI_TEST_AUTOMATION\backend\app\schemas.py`:
```python
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    name: str | None = Field(default=None, max_length=255)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    name: str | None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
```

Also add `email-validator` to deps (pydantic[email] dependency).

In `backend/pyproject.toml`, change `"pydantic>=2.9,<3"` to `"pydantic[email]>=2.9,<3"`, then:

```bash
pip install -e ".[dev]"
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
pytest tests/test_schemas.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas.py backend/tests/test_schemas.py backend/pyproject.toml
git commit -m "feat(schemas): add User and Token Pydantic schemas"
```

---

## Task 8: Auth service — password hashing + JWT

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\backend\app\auth\__init__.py`
- Create: `C:\AI_TEST_AUTOMATION\backend\app\auth\service.py`
- Create: `C:\AI_TEST_AUTOMATION\backend\tests\test_auth_service.py`

- [ ] **Step 1: Write failing test**

Write `C:\AI_TEST_AUTOMATION\backend\tests\test_auth_service.py`:
```python
import time
import uuid

import pytest
from jose import jwt

from app.auth.service import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_round_trip():
    h = hash_password("hunter2hunter2")
    assert h != "hunter2hunter2"
    assert verify_password("hunter2hunter2", h) is True
    assert verify_password("wrong-password", h) is False


def test_jwt_round_trip(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_EXPIRES_MINUTES", "60")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    from app.config import get_settings
    get_settings.cache_clear()

    user_id = uuid.uuid4()
    token = create_access_token(subject=str(user_id))
    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["exp"] > time.time()


def test_jwt_decode_rejects_garbage(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    from app.config import get_settings
    get_settings.cache_clear()

    with pytest.raises(jwt.JWTError):
        decode_access_token("not.a.jwt")
```

- [ ] **Step 2: Run test, verify it fails**

```bash
pytest tests/test_auth_service.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.auth'`.

- [ ] **Step 3: Implement auth service**

Create `C:\AI_TEST_AUTOMATION\backend\app\auth\__init__.py` (empty file).

Write `C:\AI_TEST_AUTOMATION\backend\app\auth\service.py`:
```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt
from passlib.context import CryptContext

from app.config import get_settings

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.jwt_expires_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_auth_service.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth/__init__.py backend/app/auth/service.py backend/tests/test_auth_service.py
git commit -m "feat(auth): add password hashing and JWT issue/decode"
```

---

## Task 9: FastAPI app skeleton + deps

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\backend\app\main.py`
- Create: `C:\AI_TEST_AUTOMATION\backend\app\deps.py`
- Create: `C:\AI_TEST_AUTOMATION\backend\tests\conftest.py`
- Create: `C:\AI_TEST_AUTOMATION\backend\tests\test_main.py`

- [ ] **Step 1: Write pytest fixtures**

Write `C:\AI_TEST_AUTOMATION\backend\tests\conftest.py`:
```python
from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Force test env vars BEFORE importing app
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("JWT_EXPIRES_MINUTES", "60")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")

from app.config import get_settings  # noqa: E402
from app.db import Base, get_db, get_engine, get_sessionmaker  # noqa: E402
from app.main import create_app  # noqa: E402

get_settings.cache_clear()
get_engine.cache_clear()
get_sessionmaker.cache_clear()


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
```

- [ ] **Step 2: Write failing test**

Write `C:\AI_TEST_AUTOMATION\backend\tests\test_main.py`:
```python
from httpx import AsyncClient


async def test_health_endpoint(client: AsyncClient) -> None:
    r = await client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

- [ ] **Step 3: Run test, verify it fails**

```bash
pytest tests/test_main.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.main'`.

- [ ] **Step 4: Implement deps**

Write `C:\AI_TEST_AUTOMATION\backend\app\deps.py`:
```python
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import decode_access_token
from app.db import get_db
from app.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        sub = payload.get("sub")
        if not sub:
            raise credentials_error
        user_id = uuid.UUID(sub)
    except (JWTError, ValueError) as e:
        raise credentials_error from e

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_error
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
```

- [ ] **Step 5: Implement main**

Write `C:\AI_TEST_AUTOMATION\backend\app\main.py`:
```python
from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield


def create_app() -> FastAPI:
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

    # Routers wired in later tasks
    from app.auth.router import router as auth_router
    app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])

    return app


app = create_app()
```

(The `auth.router` import will fail until Task 10. That's expected — we'll create the router in the next task.)

- [ ] **Step 6: Skip Task 9 test temporarily**

The test in `test_main.py` needs the auth router to import. Add `@pytest.mark.skip(reason="auth router added in task 10")` to `test_health_endpoint` for now. We'll un-skip it in Task 10.

```python
import pytest
from httpx import AsyncClient


@pytest.mark.skip(reason="auth router added in task 10")
async def test_health_endpoint(client: AsyncClient) -> None:
    r = await client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/main.py backend/app/deps.py backend/tests/conftest.py backend/tests/test_main.py
git commit -m "feat(app): add FastAPI skeleton, CORS, health, deps"
```

---

## Task 10: Auth router — register, login, me

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\backend\app\auth\router.py`
- Modify: `C:\AI_TEST_AUTOMATION\backend\tests\test_main.py` (un-skip health test)
- Create: `C:\AI_TEST_AUTOMATION\backend\tests\test_auth_router.py`

- [ ] **Step 1: Write failing tests**

Write `C:\AI_TEST_AUTOMATION\backend\tests\test_auth_router.py`:
```python
from httpx import AsyncClient

VALID_PWD = "supersecretpw"


async def test_register_creates_user(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": "alice@example.com", "password": VALID_PWD, "name": "Alice"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["email"] == "alice@example.com"
    assert body["name"] == "Alice"
    assert "password" not in body
    assert "id" in body


async def test_register_rejects_duplicate(client: AsyncClient) -> None:
    payload = {"email": "bob@example.com", "password": VALID_PWD}
    r1 = await client.post("/api/v1/auth/register", json=payload)
    assert r1.status_code == 201
    r2 = await client.post("/api/v1/auth/register", json=payload)
    assert r2.status_code == 409


async def test_login_returns_token(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "carol@example.com", "password": VALID_PWD},
    )
    r = await client.post(
        "/api/v1/auth/login",
        data={"username": "carol@example.com", "password": VALID_PWD},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)
    assert len(body["access_token"]) > 20


async def test_login_rejects_bad_password(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "dave@example.com", "password": VALID_PWD},
    )
    r = await client.post(
        "/api/v1/auth/login",
        data={"username": "dave@example.com", "password": "wrong-password!!"},
    )
    assert r.status_code == 401


async def test_me_requires_token(client: AsyncClient) -> None:
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401


async def test_me_returns_user_when_authenticated(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "eve@example.com", "password": VALID_PWD, "name": "Eve"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        data={"username": "eve@example.com", "password": VALID_PWD},
    )
    token = login.json()["access_token"]
    r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "eve@example.com"
```

- [ ] **Step 2: Remove the skip in `test_main.py`**

Edit `C:\AI_TEST_AUTOMATION\backend\tests\test_main.py` to remove `@pytest.mark.skip` and the import.

- [ ] **Step 3: Implement the router**

Write `C:\AI_TEST_AUTOMATION\backend\app\auth\router.py`:
```python
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.auth.service import create_access_token, hash_password, verify_password
from app.deps import CurrentUser, DbSession
from app.models import User
from app.schemas import TokenResponse, UserCreate, UserRead

router = APIRouter()


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, db: DbSession) -> User:
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        name=payload.name,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered") from e
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == form.username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(subject=str(user.id))
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserRead)
async def me(user: CurrentUser) -> User:
    return user
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
pytest tests/ -v
```

Expected: all green (config, db, schemas, auth_service, main health, 6 auth_router tests).

- [ ] **Step 5: Quick manual smoke**

In one terminal:
```bash
docker compose up -d postgres
cd backend
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

In another:
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"smoke@test.com","password":"supersecretpw","name":"Smoke"}'

TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=smoke@test.com&password=supersecretpw" | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl http://localhost:8000/api/v1/auth/me -H "Authorization: Bearer $TOKEN"
```

Expected: `{"id":"<uuid>","email":"smoke@test.com","name":"Smoke","created_at":"..."}`.

Also open http://localhost:8000/docs in a browser — the auto-generated Swagger UI should show 3 endpoints under "auth".

- [ ] **Step 6: Commit**

```bash
git add backend/app/auth/router.py backend/tests/test_auth_router.py backend/tests/test_main.py
git commit -m "feat(auth): add register, login, and /me endpoints with tests"
```

---

## Task 11: Frontend scaffold — Vite + React + TS + Tailwind

**Files:**
- All under `C:\AI_TEST_AUTOMATION\frontend\`

- [ ] **Step 1: Create Vite project**

From `C:\AI_TEST_AUTOMATION\`:
```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
```

- [ ] **Step 2: Install Tailwind CSS**

```bash
npm install -D tailwindcss@^3 postcss autoprefixer
npx tailwindcss init -p
```

(Note: shadcn/ui currently supports Tailwind v3; if v4 is the only available major when you run this, follow shadcn's docs for v4 setup.)

- [ ] **Step 3: Configure Tailwind**

Edit `C:\AI_TEST_AUTOMATION\frontend\tailwind.config.js`:
```js
/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: [
    "./index.html",
    "./src/**/*.{ts,tsx}",
  ],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: { "2xl": "1400px" },
    },
    extend: {},
  },
  plugins: [],
}
```

Replace `C:\AI_TEST_AUTOMATION\frontend\src\index.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  font-family: ui-sans-serif, system-ui, sans-serif;
}
```

- [ ] **Step 4: Install runtime deps**

```bash
npm install react-router-dom@^6 @tanstack/react-query@^5 axios@^1 zustand@^4
```

- [ ] **Step 5: Configure TS path alias**

Edit `C:\AI_TEST_AUTOMATION\frontend\tsconfig.json`. Inside `compilerOptions` add:
```json
"baseUrl": ".",
"paths": { "@/*": ["./src/*"] }
```

Edit `C:\AI_TEST_AUTOMATION\frontend\vite.config.ts`:
```ts
import path from "node:path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: { port: 5173 },
})
```

- [ ] **Step 6: Initialize shadcn/ui**

```bash
npx shadcn@latest init
```

When prompted, accept defaults; "Style: Default", "Base color: Slate", set CSS variables: Yes, configure path aliases as configured.

Add components we'll need this week:
```bash
npx shadcn@latest add button input label card form toast
```

- [ ] **Step 7: Run dev server to verify**

```bash
npm run dev
```

Open http://localhost:5173. Expected: default Vite + React page renders. Stop with Ctrl+C.

- [ ] **Step 8: Commit**

```bash
cd ..
git add frontend/
git commit -m "chore(frontend): scaffold Vite + React + TS + Tailwind + shadcn/ui"
```

---

## Task 12: Frontend API client + auth store + types

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\frontend\src\api\client.ts`
- Create: `C:\AI_TEST_AUTOMATION\frontend\src\api\auth.ts`
- Create: `C:\AI_TEST_AUTOMATION\frontend\src\api\types.ts`
- Create: `C:\AI_TEST_AUTOMATION\frontend\src\hooks\useAuthStore.ts`

- [ ] **Step 1: Create API types**

Write `C:\AI_TEST_AUTOMATION\frontend\src\api\types.ts`:
```ts
export interface User {
  id: string
  email: string
  name: string | null
  created_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: "bearer"
}

export interface RegisterPayload {
  email: string
  password: string
  name?: string
}

export interface LoginPayload {
  email: string
  password: string
}

export interface ApiError {
  detail: string
}
```

- [ ] **Step 2: Create axios client with interceptor**

Write `C:\AI_TEST_AUTOMATION\frontend\src\api\client.ts`:
```ts
import axios, { type AxiosInstance } from "axios"

const API_BASE = "http://localhost:8000/api/v1"

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
})

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token")
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("access_token")
      if (window.location.pathname !== "/login" && window.location.pathname !== "/register") {
        window.location.href = "/login"
      }
    }
    return Promise.reject(error)
  },
)
```

- [ ] **Step 3: Create auth API functions**

Write `C:\AI_TEST_AUTOMATION\frontend\src\api\auth.ts`:
```ts
import axios from "axios"

import { apiClient } from "./client"
import type { LoginPayload, RegisterPayload, TokenResponse, User } from "./types"

export async function register(payload: RegisterPayload): Promise<User> {
  const { data } = await apiClient.post<User>("/auth/register", payload)
  return data
}

export async function login(payload: LoginPayload): Promise<TokenResponse> {
  // FastAPI's OAuth2PasswordRequestForm uses form-urlencoded
  const body = new URLSearchParams()
  body.set("username", payload.email)
  body.set("password", payload.password)
  const { data } = await axios.post<TokenResponse>(
    "http://localhost:8000/api/v1/auth/login",
    body,
    { headers: { "Content-Type": "application/x-www-form-urlencoded" } },
  )
  return data
}

export async function getMe(): Promise<User> {
  const { data } = await apiClient.get<User>("/auth/me")
  return data
}
```

- [ ] **Step 4: Create Zustand auth store**

Write `C:\AI_TEST_AUTOMATION\frontend\src\hooks\useAuthStore.ts`:
```ts
import { create } from "zustand"

import type { User } from "@/api/types"

interface AuthState {
  user: User | null
  token: string | null
  setAuth: (token: string, user: User) => void
  setUser: (user: User) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: typeof window !== "undefined" ? localStorage.getItem("access_token") : null,
  setAuth: (token, user) => {
    localStorage.setItem("access_token", token)
    set({ token, user })
  },
  setUser: (user) => set({ user }),
  logout: () => {
    localStorage.removeItem("access_token")
    set({ token: null, user: null })
  },
}))
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api frontend/src/hooks
git commit -m "feat(frontend): add API client, auth functions, and Zustand store"
```

---

## Task 13: Protected route + App router

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\frontend\src\components\ProtectedRoute.tsx`
- Modify: `C:\AI_TEST_AUTOMATION\frontend\src\App.tsx`
- Modify: `C:\AI_TEST_AUTOMATION\frontend\src\main.tsx`

- [ ] **Step 1: Write ProtectedRoute**

Write `C:\AI_TEST_AUTOMATION\frontend\src\components\ProtectedRoute.tsx`:
```tsx
import { useQuery } from "@tanstack/react-query"
import type { ReactNode } from "react"
import { Navigate } from "react-router-dom"

import { getMe } from "@/api/auth"
import { useAuthStore } from "@/hooks/useAuthStore"

interface Props {
  children: ReactNode
}

export function ProtectedRoute({ children }: Props) {
  const token = useAuthStore((s) => s.token)
  const setUser = useAuthStore((s) => s.setUser)

  const { data, isLoading, isError } = useQuery({
    queryKey: ["me"],
    queryFn: getMe,
    enabled: !!token,
    retry: false,
  })

  if (!token) return <Navigate to="/login" replace />

  if (isLoading) {
    return <div className="p-8 text-center text-slate-500">Loading…</div>
  }

  if (isError || !data) return <Navigate to="/login" replace />

  // hydrate store
  if (!useAuthStore.getState().user) {
    setUser(data)
  }

  return <>{children}</>
}
```

- [ ] **Step 2: Replace `src/main.tsx`**

Write `C:\AI_TEST_AUTOMATION\frontend\src\main.tsx`:
```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import React from "react"
import ReactDOM from "react-dom/client"
import { BrowserRouter } from "react-router-dom"

import App from "./App"
import "./index.css"

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, refetchOnWindowFocus: false } },
})

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
)
```

- [ ] **Step 3: Replace `src/App.tsx`**

Write `C:\AI_TEST_AUTOMATION\frontend\src\App.tsx`:
```tsx
import { Navigate, Route, Routes } from "react-router-dom"

import { ProtectedRoute } from "@/components/ProtectedRoute"
import Dashboard from "@/pages/Dashboard"
import Login from "@/pages/Login"
import Register from "@/pages/Register"

function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}

export default App
```

(Pages don't exist yet — TS will complain. Next task fixes that.)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components frontend/src/main.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add ProtectedRoute, router, QueryClient provider"
```

---

## Task 14: Login, Register, Dashboard pages

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\frontend\src\pages\Login.tsx`
- Create: `C:\AI_TEST_AUTOMATION\frontend\src\pages\Register.tsx`
- Create: `C:\AI_TEST_AUTOMATION\frontend\src\pages\Dashboard.tsx`

- [ ] **Step 1: Write Login page**

Write `C:\AI_TEST_AUTOMATION\frontend\src\pages\Login.tsx`:
```tsx
import { useMutation } from "@tanstack/react-query"
import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"

import { getMe, login } from "@/api/auth"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useAuthStore } from "@/hooks/useAuthStore"

export default function Login() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()
  const setAuth = useAuthStore((s) => s.setAuth)

  const mutation = useMutation({
    mutationFn: async () => {
      const { access_token } = await login({ email, password })
      localStorage.setItem("access_token", access_token)
      const user = await getMe()
      setAuth(access_token, user)
    },
    onSuccess: () => navigate("/dashboard"),
    onError: (err: unknown) => {
      const msg =
        // axios-shaped error
        (err as { response?: { data?: { detail?: string } } }).response?.data?.detail ??
        "Login failed"
      setError(msg)
    },
  })

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Log in</CardTitle>
          <CardDescription>Welcome back</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault()
              setError(null)
              mutation.mutate()
            }}
          >
            <div className="space-y-1">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <Button type="submit" className="w-full" disabled={mutation.isPending}>
              {mutation.isPending ? "Logging in…" : "Log in"}
            </Button>
            <p className="text-sm text-center text-slate-600">
              No account?{" "}
              <Link to="/register" className="underline">
                Register
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
```

- [ ] **Step 2: Write Register page**

Write `C:\AI_TEST_AUTOMATION\frontend\src\pages\Register.tsx`:
```tsx
import { useMutation } from "@tanstack/react-query"
import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"

import { getMe, login, register } from "@/api/auth"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useAuthStore } from "@/hooks/useAuthStore"

export default function Register() {
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()
  const setAuth = useAuthStore((s) => s.setAuth)

  const mutation = useMutation({
    mutationFn: async () => {
      await register({ email, password, name: name || undefined })
      const { access_token } = await login({ email, password })
      localStorage.setItem("access_token", access_token)
      const user = await getMe()
      setAuth(access_token, user)
    },
    onSuccess: () => navigate("/dashboard"),
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } }).response?.data?.detail ??
        "Registration failed"
      setError(msg)
    },
  })

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Create your account</CardTitle>
          <CardDescription>Get started</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault()
              setError(null)
              mutation.mutate()
            }}
          >
            <div className="space-y-1">
              <Label htmlFor="name">Name (optional)</Label>
              <Input id="name" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="password">Password (min 12 chars)</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={12}
                required
              />
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <Button type="submit" className="w-full" disabled={mutation.isPending}>
              {mutation.isPending ? "Creating…" : "Create account"}
            </Button>
            <p className="text-sm text-center text-slate-600">
              Already have an account?{" "}
              <Link to="/login" className="underline">
                Log in
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
```

- [ ] **Step 3: Write Dashboard page (placeholder for W2)**

Write `C:\AI_TEST_AUTOMATION\frontend\src\pages\Dashboard.tsx`:
```tsx
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useAuthStore } from "@/hooks/useAuthStore"

export default function Dashboard() {
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)

  return (
    <div className="min-h-screen bg-slate-50 p-8">
      <header className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-semibold">API Test Platform</h1>
        <div className="flex items-center gap-4">
          <span className="text-sm text-slate-600">{user?.email}</span>
          <Button
            variant="outline"
            onClick={() => {
              logout()
              window.location.href = "/login"
            }}
          >
            Log out
          </Button>
        </div>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Welcome, {user?.name ?? user?.email}</CardTitle>
          <CardDescription>
            Projects, specs, and test suites will live here from Week 2 onward.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-slate-600">
            This dashboard is currently a placeholder. Authentication is fully wired up — you reached
            this page because your JWT was valid.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
```

- [ ] **Step 4: Run dev server and end-to-end smoke**

In one terminal (backend):
```bash
docker compose up -d postgres
cd backend
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

In another (frontend):
```bash
cd frontend
npm run dev
```

In a browser at http://localhost:5173:
1. You should be redirected to `/login`.
2. Click "Register" → fill in a fresh email and a ≥12-char password → submit.
3. You should land on `/dashboard` showing your email.
4. Refresh the page — still on `/dashboard` (token persists in localStorage).
5. Click "Log out" → back to `/login`.
6. Log in with the same credentials → back to `/dashboard`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages
git commit -m "feat(frontend): add Login, Register, and placeholder Dashboard pages"
```

---

## Task 15: CI workflow

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\.github\workflows\ci.yml`

- [ ] **Step 1: Write CI workflow**

Write `C:\AI_TEST_AUTOMATION\.github\workflows\ci.yml`:
```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: apitest
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready --health-interval 5s
          --health-timeout 3s --health-retries 5
    defaults:
      run:
        working-directory: backend
    env:
      DATABASE_URL: sqlite+aiosqlite:///:memory:
      JWT_SECRET: ci-test-secret
      JWT_ALGORITHM: HS256
      JWT_EXPIRES_MINUTES: "60"
      CORS_ORIGINS: http://localhost:5173
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - run: pip install --upgrade pip
      - run: pip install -e ".[dev]"
      - run: ruff check .
      - run: mypy app
      - run: pytest -v

  frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
      - run: npm run build
```

- [ ] **Step 2: Verify locally that backend checks pass**

```bash
cd backend
ruff check .
mypy app
pytest -v
```

If `ruff` flags issues, run `ruff check --fix .` then re-run. Fix any `mypy` complaints in place. All tests should pass.

- [ ] **Step 3: Verify frontend builds**

```bash
cd ../frontend
npm run build
```

Expected: produces `frontend/dist/` without errors.

- [ ] **Step 4: Commit**

```bash
cd ..
git add .github/workflows/ci.yml
git commit -m "ci: add GitHub Actions for ruff, mypy, pytest, and frontend build"
```

---

## Task 16: ADR-001 + Week 1 closeout

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\docs\adr\001-modular-monolith.md`

- [ ] **Step 1: Write ADR-001**

Write `C:\AI_TEST_AUTOMATION\docs\adr\001-modular-monolith.md`:
```markdown
# ADR-001: Modular Monolith over Microservices

**Status:** Accepted
**Date:** 2026-05-14

## Context

We need to decide the deployment architecture for a POC API test generation
platform with auth, spec ingestion, LLM-driven generation, HTTP-based test
execution, and an agentic loop. Time budget is 8 weeks with a 2-week vacation
in the middle.

## Decision

Build as a single FastAPI process composed of strictly-bounded internal modules
(`auth`, `specs`, `llm`, `generator`, `runner`, `analyzer`, `agentic`, `reports`).
Modules communicate via typed service-function calls. The agentic loop is the
only piece with a non-trivial control-flow story; it is implemented via LangGraph
within the same process.

## Alternatives Considered

- **Microservices** — rejected. Doubles plumbing work (auth across services,
  distributed logging, service discovery) for no scale benefit at one-user POC scale.
- **Event-driven (Celery + Redis)** — rejected. Async-job complexity is not
  justified at our load profile (≤ 10 concurrent runs).

## Consequences

**Positive**
- Single deployable image, simple local dev, fast iteration.
- Module boundaries can be extracted to services later without rewriting domain logic.
- Easier to debug across a 2-week vacation gap.

**Negative / Trade-offs**
- No horizontal scaling story out of the box — acceptable for POC.
- Long-running LLM calls + agentic loops live in the same process as the API;
  we mitigate with FastAPI `BackgroundTasks` and Postgres-backed LangGraph checkpoints.
```

- [ ] **Step 2: Final verification of the gate**

The week's gate is: `docker compose up` → register → login → see authenticated dashboard placeholder.

Verify the full flow one more time:
1. `docker compose up -d` (Postgres + VAmPI running).
2. `cd backend && alembic upgrade head && uvicorn app.main:app --reload --port 8000`
3. `cd frontend && npm run dev`
4. Browser at http://localhost:5173 → register → land on `/dashboard` → log out → log in → `/dashboard`.

If anything's broken, fix before declaring W1 done.

- [ ] **Step 3: Run full test suite + lint**

```bash
cd backend
ruff check .
mypy app
pytest -v
```

All green.

- [ ] **Step 4: Commit closeout**

```bash
cd ..
git add docs/adr/001-modular-monolith.md
git commit -m "docs: add ADR-001 modular monolith"
git tag week-1-complete
```

---

## Verification Checklist (end of Week 1)

- [ ] `docker compose up -d` brings up Postgres (healthy) + VAmPI (`curl http://localhost:5001/` returns 200)
- [ ] `alembic upgrade head` creates `users` table in Postgres
- [ ] `uvicorn app.main:app --reload` starts cleanly; `/docs` shows auth endpoints
- [ ] `POST /api/v1/auth/register` returns 201 with user JSON (no `password` field)
- [ ] Duplicate registration returns 409
- [ ] `POST /api/v1/auth/login` (form-encoded) returns `access_token`
- [ ] Bad password returns 401
- [ ] `GET /api/v1/auth/me` returns user when given valid bearer token, 401 otherwise
- [ ] Frontend at `http://localhost:5173`:
  - `/` redirects to `/login` when logged out, `/dashboard` when logged in
  - Register flow lands on `/dashboard` showing user email
  - Refresh on `/dashboard` keeps session
  - Logout returns to `/login`
- [ ] `pytest -v` — all green
- [ ] `ruff check .` — clean
- [ ] `mypy app` — clean
- [ ] `npm run build` succeeds in `frontend/`
- [ ] CI workflow file exists at `.github/workflows/ci.yml`

When all 16 boxes are ticked, you are done with Week 1.

---

## Notes for Week 2

Week 2 will add the `Project`, `Spec`, and `Endpoint` tables, the `app/specs/` module with OpenAPI parsing via `prance`, the project/spec upload UI, and an endpoint browser. It depends on the user-scoped auth from W1 (`get_current_user` is the ownership boundary).
