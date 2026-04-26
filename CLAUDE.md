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

**Entry point:** `main.py` — FastAPI app with a lifespan that: creates all tables, runs `ensure_compatible_schema()` (ad-hoc DDL patcher), seeds from YAML configs, calls `ensure_demo_session(db)` to (re)hydrate the shared demo session, and starts an APScheduler daily crawl at 08:00 Asia/Shanghai + an hourly guest-cleanup interval job.

**Routers:** `jobs`, `tracks`, `scoring`, `exclude`, `crawl`, `export`, `scheduler`, `system_config`, `company_recrawl`, `job_intel`, `resume_copilot`, `sites`. Each router is a file under `app/routers/`.

**Database:** Single SQLite file at `backend/data/jobradar.db`. WAL mode and `busy_timeout=5000` are set via a SQLAlchemy `@event.listens_for(engine, 'connect')` hook. Models are in `app/models.py`; schema evolution is handled by `app/services/schema_patch.py` (not Alembic — see Q10 in the review plan if you want to migrate this).

**Resume Copilot pipeline** (`app/services/resume_copilot/`):
- `workflow.py` — two async-safe workflows: `run_resume_parse_workflow` and `run_resume_generate_workflow`, both dispatched via FastAPI `BackgroundTasks`. Each opens its own `SessionLocal`.
- `parser.py` — calls an LLM to extract structured profile from raw PDF text; falls back to heuristic extraction on HTTP errors.
- `ingest.py` — `extract_resume_text_with_page_count(bytes) -> (text, page_count)` is the canonical PDF-extract helper; `extract_resume_text_from_pdf` is a thin wrapper kept for older call sites. `POST /sessions` returns `page_count` and `file_size_bytes` so the upload UI can show real numbers in its agent trace.
- `recommendation.py` — pre-filters jobs from DB by preferences/track, scores with `compute_rule_score`, optionally enriches with `JobIntelSnapshot` boosts (14-day TTL). LLM reranks top-N results.
- `quick_enrichment.py` — parallel web search + page extraction for top-N jobs using `ThreadPoolExecutor`. Trace events are collected in thread-local lists and replayed in the main thread to avoid concurrent SQLite writes.
- `feedback.py` — LLM-generated resume diagnostics and rewrite suggestions.
- `demo_session.py` — `DEMO_SESSION_ID = 1` + `ensure_demo_session(db)`. Seeds a fully-prepared shared session (张三 / 上交大本科 / 互联网数据分析) with `user_key='__demo__'`, `is_guest=0`, status `completed`, and pre-computed recommendations + direction analysis + 3 chat messages. The lifespan calls this on every startup; existing demo rows are force-updated to ensure `user_key='__demo__'` is set (so the read-only guard catches them).

**Demo session read-only guard**: in `routers/resume_copilot.py`, `_assert_not_demo(session)` checks `session.user_key == '__demo__'` (not session_id, so tests using id=1 with a different user_key pass). It must be called **after** `_get_session_or_404` and is mounted on every write endpoint (PATCH/DELETE session, PUT confirmed-profile, PUT preferences, POST generate, POST chat, POST chat/apply-rewrite). All `GET` endpoints are unaffected.

**Config** (`app/config.py`): reads `.env.local` from `backend/` then root, then OS env. Key groups:
- `RESUME_COPILOT_*` — LLM base URL, API key, model name, timeouts
- `TAVILY_API_KEY`, `FIRECRAWL_API_KEY`, `JINA_API_KEY`, `BRAVE_SEARCH_API_KEY` — enrichment search
- `TATA_USERNAME` / `TATA_PASSWORD` — crawler credentials
- `ALERT_STALE_DAYS` — sites-monitor staleness threshold (default 3 days)

**Sites monitor** (`app/routers/sites.py` + `app/services/{company_crawl_logger,sites_alert,company_crawler_registry}.py`):
- New table `company_crawl_logs` — per-company run record, parent-linked to `crawl_logs.id` for the daily batch.
- Context manager `company_crawl_log(db, source=, company=, parent_log_id=)` wraps each per-target call inside the orchestrators (`internet_crawler`, `state_owned_crawler`, `securities_crawler`, `consumer_foreign_crawler`). On exception: marks row `failed`, truncates `error_message` to 500 chars, re-raises. Body sets `log.fetched_count` / `log.new_count`.
- For orchestrators whose existing inner except SWALLOWS exceptions (state_owned, consumer_foreign, internet), the wrap uses a `target_exc` sentinel: inner except saves exc + still appends to results / rolls back; after the inner finally an `if target_exc is not None: raise target_exc` propagates so `company_crawl_log` marks row failed; an outer `try/except: pass` swallows for continue-on-error. Securities re-raises naturally — simple wrap.
- Energy and antgroup are explicitly **out of scope**: `energy_crawler.py` is a CLI-only standalone script not invoked by the daily cron. `crawl_antgroup` flows through `crawl_internet_targets` so it's covered transitively by the internet wrap.
- 4 endpoints under `/api/sites/*`: `GET /summary`, `GET /?source=`, `GET /{company}/runs?limit=`, `POST /{company}/recrawl`. Recrawl validates against `COMPANY_CRAWLERS` registry (16 internet t1 companies; 网易雷火 deliberately omitted because `build_internet_targets()` doesn't return targets for it), schedules a fresh `SessionLocal` background task, runs scoring on `new_count > 0` (scorer failure non-fatal — doesn't escalate to parent CrawlLog status), returns `{parent_log_id, message}`.
- Alert level rule (`alert_level(runs, now)`, pure): empty=`unknown`; last failed + prev failed=`red`; last failed alone=`yellow`; last success + no new in `ALERT_STALE_DAYS`=`yellow`; else `green`.
- `_shanghai_today_start()` returns Asia/Shanghai today 00:00 expressed as naive UTC. Fixed +08:00 offset (Asia/Shanghai never observes DST).
- `_build_site_rows` is N+1 by design: 2N+1 queries per `/api/sites` call. Acceptable at current scale (~30 companies, SQLite WAL); revisit if registry grows past ~50.

### Frontend (`frontend/src/`)

Vite + React 19 + React Router 7 + Ant Design 6. All API calls go through an Axios instance with `baseURL: '/api'`, proxied to the backend by Vite (`vite.config.ts`). Pages: `Jobs`, `JobIntel`, `Tracks`, `Scoring`, `Exclude`, `Crawl`, `Scheduler`, `Login`. There are no SSR concerns.

### Resume Copilot Web (`resume-copilot-web/`)

Next.js 16 App Router + Tailwind CSS 4 + Ant Design 6. All API calls are proxied via `next.config.ts` rewrites: `/api/:path*` → `${RESUME_COPILOT_BACKEND_URL}/api/:path*` (default `http://127.0.0.1:8002`).

**Routes**:

| Path | Component | Notes |
|---|---|---|
| `/` | `<HFHero/>` from `components/hifi/hifi-hero.tsx` | Public marketing page (HiFi terracotta). CTAs `上传简历` / `看示例推荐` open `<GuestLoginModal/>` if not logged in. |
| `/upload` | `<HFUpload/>` from `components/hifi/hifi-upload.tsx` | Single-page upload + 3-stage real parse trace (read PDF → LLM extract → ready). Client-side guard: redirects to `/` if `!isGuestUser()`. |
| `/resume-copilot?sessionId=X` | `public-resume-copilot.tsx` | Workspace. `sessionId=1` shows `<DemoBanner/>` and disables chat composer + apply-rewrite buttons. |
| `/interview/[sessionId]/check` + `/[sessionId]` | mock interview pages | Untouched by HiFi work. |
| `/login` | **deleted** | Login is a modal, not a page. |

**Two design systems coexist** (kept strictly isolated):

- **Workspace** (`/resume-copilot`) — original sky-blue palette via `var(--primary)`, `var(--ink)`, `var(--muted)`, `var(--border)`, `var(--soft-blue)`. Defined in `app/globals.css`. The agent thinking panel uses `SPINNER_FRAMES = ['·', '✢', '✳', '✶', '✻', '✽']` at **120ms** ticks with staggered per-agent start offsets (0, 2, 4), matching Claude Code terminal style. Verb cycling is 2000/2300/2600ms per agent so they don't sync.
- **HiFi** (`/`, `/upload`, `<DemoBanner/>`) — Claude terracotta system: `--terracotta` `#c96442` on `--parchment` `#f5f4ed`, Fraunces serif for headings/numbers, Inter for body, JetBrains Mono for terminal-style traces. Tokens live in `components/hifi/hifi-tokens.css` and are **scoped to `.hf`** — every HiFi root element wraps in `<div className="hf">`. Page-level layout (`hf-hero-page__*`, `hf-upload-page__*`) is in `components/hifi/hifi-pages.css` with mobile breakpoints at 1024px (single-column) and 640px (compact). Both files are imported from `app/globals.css`. **Do not** add HiFi class names to workspace components, and do not redefine workspace tokens inside `.hf`.

**Shared HiFi primitives** (`components/hifi/hifi-primitives.tsx`): `HFLogo`, `HFBtn` (primary/ghost/sand/dark/link × sm/md/lg), `HFPill` (default/amber/terra/emerald/dark), `HFTicker`, `useCountUp(target, duration)`, `useLiveCount(target, duration)` (count-up then slow live tick), and an icon set under `I.{arrowRight, upload, file, check, sparkle, ...}`.

**Auth state**: `isGuestUser()` reads `sessionStorage.jobradar.resumeCopilot.isGuest`. `markAsGuest()` sets it after `<GuestLoginModal/>` validates `guest1` / `123456`. `requestJson` in `api.ts` injects `X-Guest: 1` when this flag is set, which causes the backend to mark new sessions as `is_guest=1` (subject to 2-hour cleanup).

**Demo session constant**: `DEMO_SESSION_ID = 1` is exported from `components/resume-copilot/api.ts` and consumed by both Hero (CTA destination), Upload (`使用示例简历` button), and the workspace (`<DemoBanner/>` mount + write-disable).

Workspace key file: `components/resume-copilot/public-resume-copilot.tsx` (~1990 lines) — the entire resume copilot UI: upload → parse progress → profile editor → preference picker → recommendation cards + chat rail. It polls the backend at 1.6s intervals while `sessionIsActive(session)` is true.

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
