# Week 8 Implementation Plan — Deploy & Demo

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Polish the application, deploy it live to the cloud (Render/Railway), and prepare the recorded demo. Optionally add JSON export for reports.

**Architecture:** We add a production overlay for `docker-compose` (`docker-compose.prod.yml`). The `reports` module is built to aggregate stats and export them to JSON. The frontend is polished for the demo.

**Tech Stack Additions:** Cloud PaaS (e.g., Render.com configuration).

**Verification gate:** The application is accessible on a public URL. A user can log in, upload a spec, run a test, and download the results as JSON. The 5-minute demo video is recorded and ready.

---

## File Structure for Week 8

**Repo root (`C:\AI_TEST_AUTOMATION\`):**
- Create: `docker-compose.prod.yml`
- Create: `render.yaml` (if using Render for deployment)
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Create: `sample-api/main.py`, `sample-api/openapi.json`, `sample-api/Dockerfile`
- Create: `backend/seeds/sample_specs/vampi.json`, `backend/seeds/sample_specs/sample-api.json`

**Backend (`backend/`):**
- Create: `app/reports/__init__.py`, `app/reports/router.py`, `app/reports/export.py`
- Modify: `app/main.py` — include `reports.router`

**Frontend (`frontend/`):**
- Create: `src/pages/CoverageReport.tsx` (optional view)
- Modify: `src/pages/RunDetail.tsx` — Add "Export JSON" button

---

## Task 1: Reports Module (JSON Export)

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\backend\app\reports\__init__.py`
- Create: `C:\AI_TEST_AUTOMATION\backend\app\reports\export.py`
- Create: `C:\AI_TEST_AUTOMATION\backend\app\reports\router.py`
- Modify: `C:\AI_TEST_AUTOMATION\backend\app\main.py`

- [ ] **Step 1: Add dependencies**
In `backend/pyproject.toml` add `jinja2` for HTML report generation.

- [ ] **Step 2: Write export logic**
In `app/reports/export.py`, create a function that takes a `run_id`, fetches the run, its `TestResult`s, the original `Test`s, and any `AIAnalysis`, and formats them into a single comprehensive JSON payload. Add an HTML export option using Jinja2 templates.

- [ ] **Step 3: Write Reports router**
In `app/reports/router.py`:
```python
import uuid
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from app.reports.export import generate_run_report
from app.deps import CurrentUser, DbSession

router = APIRouter()

@router.get("/runs/{run_id}/export")
async def export_run(run_id: uuid.UUID, user: CurrentUser, db: DbSession):
    # Verify ownership logic
    report_dict = await generate_run_report(db, run_id)
    return JSONResponse(content=report_dict)
```

- [ ] **Step 4: Wire router**
Add `reports_router` to `app/main.py`.

- [ ] **Step 5: Commit**
```bash
git add backend/app/reports/ backend/app/main.py backend/pyproject.toml
git commit -m "feat(reports): add JSON and HTML export for test runs"
```

---

## Task 2: Frontend Polish & Export Trigger

**Files:**
- Modify: `C:\AI_TEST_AUTOMATION\frontend\src\pages\RunDetail.tsx`

- [ ] **Step 1: Export Button**
Add an "Export to JSON" button in `RunDetail.tsx` that hits the `/api/v1/runs/{run_id}/export` endpoint and triggers a file download in the browser.

- [ ] **Step 2: UI Polish**
Verify there are no console errors. Ensure the app is responsive enough for a desktop demo. Clean up any placeholder text in `Dashboard.tsx`.
Add the `CoverageReport.tsx` component and register its route in `App.tsx` (e.g. `<Route path="/runs/:runId/coverage" element={<CoverageReport />} />`).

- [ ] **Step 3: Commit**
```bash
git add frontend/
git commit -m "feat(frontend): add export button, coverage route, and UI polish"
```

---

## Task 3: Production Docker & Deployment Config

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\docker-compose.prod.yml`

- [ ] **Step 1: Write Dockerfiles**
Create `backend/Dockerfile` (uvicorn runner) and `frontend/Dockerfile` (nginx serving Vite build).

- [ ] **Step 2: Production Compose File**
Write `docker-compose.prod.yml` to define the production setup (stripping out VAmPI as that will run separately or not at all in prod, keeping only postgres, backend, and frontend).
*Alternatively*, configure Render `render.yaml` if deploying to Render.com using their native services (Web Service for backend, Static Site for frontend, PostgreSQL for DB).

- [ ] **Step 3: Sample API and Seed Data**
Create the bundled `sample-api/` with a simple FastAPI app, an `openapi.json`, and a `Dockerfile` for fallback demo purposes.
Create `backend/seeds/sample_specs/vampi.json` and `backend/seeds/sample_specs/sample-api.json` so they are easily accessible during the demo.

- [ ] **Step 4: Dry-run build**
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
```

- [ ] **Step 5: Commit**
```bash
git add docker-compose.prod.yml backend/Dockerfile frontend/Dockerfile sample-api/ backend/seeds/
git commit -m "chore(infra): add production deployment configs and sample demo data"
```

---

## Task 4: Demo Preparation

**Files:**
- Create: `C:\AI_TEST_AUTOMATION\backend\seeds\demo_seed.py`

> **Why a seed script is required:** The agentic loop's continuation condition depends on the coverage analyzer finding HIGH-severity gaps (Fix 1 wired actual run results into gap analysis). Whether the loop visibly iterates 2-3 times is therefore **not guaranteed** without controlling the initial test set. A seed script removes this non-determinism.

**Steps:**
- [ ] **Step 1: Create Demo Seed Script**
Create `backend/seeds/demo_seed.py` that pre-populates the database with a specific set of tests **known to pass** against VAmPI's happy-path GET endpoints (e.g., `GET /` health check, `GET /users/v1` list users). These must be validated against VAmPI before recording.

The seed script should:
1. Create a project + spec + test suite for VAmPI.
2. Insert ~4-6 happy-path tests (only `positive` scenario type, only GET endpoints with `status_eq: 200` assertions).
3. **Not** include any security tests (auth_bypass, BOLA, injection) — these are the gaps the analyzer should discover.
4. Include a docstring pinning the VAmPI image tag the seed was validated against:
```python
"""Demo seed for VAmPI.

IMPORTANT: This seed is validated against erev0s/vampi:latest (pinned in
docker-compose.yml). If you update the VAmPI image tag, re-validate that
the happy-path GET tests below still pass before recording the demo.
Failure to do this will cause the demo loop to behave unpredictably.
"""
```

- [ ] **Step 2: Script the Demo**
Write a script covering:
  - Problem framing (0-30s)
  - Login / Dashboard (30s-1m)
  - Upload VAmPI spec (1m-1m45s)
  - **Run seed script** to load the known-passing happy-path tests (1m45s-2m)
  - Run agentic loop — first run executes seed tests (all pass, partial coverage) → analyzer finds HIGH gaps (no security tests exist) → generator creates security tests → second run (2m-3m30s)
  - Show lineage tree growing, point at auto-generated BOLA/IDOR test (3m30s-4m)
  - Failure analysis & Coverage gaps (4m-4m30s)
  - Architecture & Q&A (4m30s-5m)

- [ ] **Step 3: Validate Seed Against VAmPI**
Before recording, run the seed tests against VAmPI manually to confirm they all pass:
```bash
# Ensure VAmPI is running at the pinned image tag
docker compose up -d vampi
# Run the seed
python backend/seeds/demo_seed.py
# Trigger a single run (no loop) and verify all 4-6 tests pass
```
If any seed test fails, fix the test data — do not proceed to recording with a broken seed.

- [ ] **Step 4: Record Demo**
Record the 5-minute video. Ensure VAmPI is running via docker-compose at the pinned image tag.

- [ ] **Step 5: Prepare Slide Deck**
Finalize the 5-10 slide deck covering the problem, solution, architecture diagram, and key learnings from the POC.

---

## Verification Checklist (end of Week 8)

- [ ] Application deployed and accessible over public URL (or fully verified local-prod build).
- [ ] JSON export feature works end-to-end.
- [ ] UI is polished and demo-ready.
- [ ] 5-minute demo recorded and slide deck finalized.
- [ ] All tests pass cleanly (`pytest -v`).

When all 5 boxes are ticked, the project is officially COMPLETE.
