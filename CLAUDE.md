# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

**JobRadar** is a campus-recruitment tracking tool for the Chinese job market. It has three runtimes:

| Runtime | Root | Port | Purpose |
|---|---|---|---|
| Backend API | `backend/` | 8000 (dev) / 8002 (resume-copilot docker) | FastAPI + SQLite, all data logic |
| Frontend (job browser) | `frontend/` | 5173 | Vite + React, job search/scoring/intel UI |
| Resume Copilot Web | `resume-copilot-web/` | 3001 | Next.js, resume upload → parse → recommend flow |

The frontend and resume-copilot-web are separate apps that both proxy `/api/*` to the same backend. They are never served together in dev.

---

## Commands

### Backend
```bash
# Install deps (from repo root or backend/)
cd backend && pip install -r requirements.txt

# Run dev server (port 8000)
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Run all tests
cd backend && PYTHONPATH=. .venv/bin/pytest tests/

# Run a single test file
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_resume_copilot_service.py -x

# Run a specific test
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_resume_copilot_service.py::test_name -x
```

> `test_resume_copilot_service.py` has a pre-existing import bug (imports `ResumeRecommendationItem` from `app.models` but it lives in `schemas_resume_copilot`). Skip it when running the full suite: `pytest tests/ --ignore=tests/test_resume_copilot_service.py`.

### Frontend (Vite + React job browser)
```bash
cd frontend && npm install
npm run dev      # port 5173
npm run lint
npm run build    # tsc + vite build
npm test         # vitest
```

### Resume Copilot Web (Next.js)
```bash
cd resume-copilot-web && npm install
npm run dev      # port 3001
npm run lint     # must pass with 0 errors before shipping
npm run build    # next build
```

### Docker (both backend + frontend together)
```bash
docker compose up --build
# backend → :8001, frontend → :5173
```

---

## Architecture

### Backend (`backend/app/`)

**Entry point:** `main.py` — FastAPI app with a lifespan that: creates all tables, runs `ensure_compatible_schema()` (ad-hoc DDL patcher), seeds from YAML configs, and starts an APScheduler daily crawl at 08:00 Asia/Shanghai.

**Routers:** `jobs`, `tracks`, `scoring`, `exclude`, `crawl`, `export`, `scheduler`, `system_config`, `company_recrawl`, `job_intel`, `resume_copilot`. Each router is a file under `app/routers/`.

**Database:** Single SQLite file at `backend/data/jobradar.db`. WAL mode and `busy_timeout=5000` are set via a SQLAlchemy `@event.listens_for(engine, 'connect')` hook. Models are in `app/models.py`; schema evolution is handled by `app/services/schema_patch.py` (not Alembic — see Q10 in the review plan if you want to migrate this).

**Resume Copilot pipeline** (`app/services/resume_copilot/`):
- `workflow.py` — two async-safe workflows: `run_resume_parse_workflow` and `run_resume_generate_workflow`, both dispatched via FastAPI `BackgroundTasks`. Each opens its own `SessionLocal`.
- `parser.py` — calls an LLM to extract structured profile from raw PDF text; falls back to heuristic extraction on HTTP errors.
- `recommendation.py` — pre-filters jobs from DB by preferences/track, scores with `compute_rule_score`, optionally enriches with `JobIntelSnapshot` boosts (14-day TTL). LLM reranks top-N results.
- `quick_enrichment.py` — parallel web search + page extraction for top-N jobs using `ThreadPoolExecutor`. Trace events are collected in thread-local lists and replayed in the main thread to avoid concurrent SQLite writes.
- `feedback.py` — LLM-generated resume diagnostics and rewrite suggestions.

**Config** (`app/config.py`): reads `.env.local` from `backend/` then root, then OS env. Key groups:
- `RESUME_COPILOT_*` — LLM base URL, API key, model name, timeouts
- `TAVILY_API_KEY`, `FIRECRAWL_API_KEY`, `JINA_API_KEY`, `BRAVE_SEARCH_API_KEY` — enrichment search
- `TATA_USERNAME` / `TATA_PASSWORD` — crawler credentials

### Frontend (`frontend/src/`)

Vite + React 19 + React Router 7 + Ant Design 6. All API calls go through an Axios instance with `baseURL: '/api'`, proxied to the backend by Vite (`vite.config.ts`). Pages: `Jobs`, `JobIntel`, `Tracks`, `Scoring`, `Exclude`, `Crawl`, `Scheduler`, `Login`. There are no SSR concerns.

### Resume Copilot Web (`resume-copilot-web/`)

Next.js 16 App Router + Tailwind CSS 4 + Ant Design 6. All API calls are proxied via `next.config.ts` rewrites: `/api/:path*` → `${RESUME_COPILOT_BACKEND_URL}/api/:path*` (default `http://127.0.0.1:8002`). 

Key file: `components/resume-copilot/public-resume-copilot.tsx` (~1980 lines) — the entire resume copilot UI: upload → parse progress → profile editor → preference picker → recommendation cards + chat rail. It polls the backend at 1.6s intervals while `sessionIsActive(session)` is true.

Styling uses CSS custom properties (`var(--primary)`, `var(--ink)`, `var(--muted)`, `var(--border)`, `var(--soft-blue)`). The agent thinking panel uses `SPINNER_FRAMES = ['·', '✢', '✳', '✶', '✻', '✽']` at **120ms** ticks with staggered per-agent start offsets (0, 2, 4), matching Claude Code terminal style. Verb cycling is 2000/2300/2600ms per agent so they don't sync.

### Session state machine (resume copilot)

`ResumeCopilotSession.status` transitions:
```
uploading → parsing → awaiting_user_confirmation → generating_recommendations → completed
                                                 ↘ failed
```
`recommendation_status` and `direction_status` are independent sub-statuses (`running | completed | failed`). The router derives `has_parsed_profile / has_confirmed_profile / has_recommendations / has_feedback` via `joinedload` (single JOIN query — see `_get_session_eager` in `routers/resume_copilot.py`).

**Chat rail** (feature/big-wip-20260315): Each session has a `/chat` endpoint returning `CopilotMessage[]`. Chat turns call `generate_chat_turn` in `services/resume_copilot/chat.py`, which has access to the full recommendation + direction analysis context. Rewrite suggestions can be applied via `POST /chat/apply-rewrite`.

### Root-level scripts (`scripts/`)

Standalone scripts for job filtering, reporting, and crawling — **not** part of the FastAPI app. Run from the repo root with `python scripts/<name>.py`.

Key files:
- `config.yaml` — track/keyword/scoring rules consumed by `filter_jobs_v2.py`
- `filter_jobs.py` / `filter_jobs_v2.py` — filter job CSVs by track rules
- `auto_login_scraper.py` — Playwright-based Tata Wangshen login + scrape
- `tata_jobs_export.py` — export Tata VIP job table to CSV
- `generate_report.py` — generate Markdown job recommendation report
- `jobradar-docker-*.sh` — Docker lifecycle helpers

### Data exports (`data/exports/`)

56 MB of denormalized company/job truth-layer CSVs built by the tier-annotation pipeline:
- `company_truth_spring_master.csv` — canonical company list with tier labels
- `job_truth_spring_master.csv` — canonical job list with company linkage
- `tata_aligned_to_spring_truth.csv` — Tata export aligned to truth layer
- `legal_entity_alias_*.csv` — entity resolution candidates/overrides

### Backend data scripts (`backend/scripts/`)

Periodic scripts for crawling company tier lists (consulting, internet, state-owned, securities, consumer-foreign), building the `company_truth_layer`, aligning TATA export sheets, and annotating job rows with company tiers. Run directly as `python backend/scripts/<script>.py` from the repo root.

---

## Environment setup

Create `backend/.env.local` with at minimum:
```
RESUME_COPILOT_BASE_URL=https://api.deepseek.com/v1
RESUME_COPILOT_API_KEY=sk-...
RESUME_COPILOT_MODEL_NAME=deepseek-chat
TAVILY_API_KEY=tvly-...
FIRECRAWL_API_KEY=fc-...
```

For the resume-copilot-web, set `RESUME_COPILOT_BACKEND_URL` in `resume-copilot-web/.env.local` if the backend runs on a port other than 8002.
