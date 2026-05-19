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
