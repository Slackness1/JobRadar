# JobRadar Architecture

## Purpose
- This document is the fast map for agent sessions.
- Read this when you need to understand the codebase layout, major flows, and where changes are likely to land.
- For rules, commands, and coding style, see `AGENTS.md`.

## System Snapshot
- JobRadar aggregates job data, normalizes it, stores it in SQLite, and exposes it through a FastAPI backend + React SPA frontend.
- Core stack:
  - Frontend: React 19 + TypeScript + Vite + Ant Design
  - Backend: FastAPI + SQLAlchemy + SQLite + APScheduler
  - Crawling: Requests + Playwright + config-driven adapters
- Primary runtime shape:
  - browser -> `/api/*` -> FastAPI -> SQLite
  - production can also serve built frontend assets from the backend when `frontend/dist/` exists

## Repository Map
- `backend/`: app, routers, services, models, schemas, tests, config
- `frontend/`: SPA pages, shared components, API client, Vite config
- `docs/`: playbooks, plans, decisions, architecture, deployment notes
- `scripts/`: runnable helpers for crawl, merge, deploy, validation
- `config.yaml`: seed / scoring / target configuration source

## Backend Architecture

### App entry and lifecycle
- `backend/app/main.py`
- On startup the app:
  - creates tables
  - applies schema compatibility patches
  - marks stale crawl/recrawl state failed
  - seeds from `config.yaml`
  - starts the scheduler
- The app also:
  - registers all routers
  - adds read-only guest middleware
  - configures CORS
  - serves the built SPA when `frontend/dist/` exists

### Routers
- `backend/app/routers/jobs.py`
  - list/search/filter jobs, stats, company expand, application status, CSV import
- `backend/app/routers/tracks.py`
  - tracks, groups, keywords, JSON import
- `backend/app/routers/scoring.py`
  - scoring config and rescore trigger
- `backend/app/routers/exclude.py`
  - exclude rules CRUD
- `backend/app/routers/crawl.py`
  - crawl trigger, logs, status
- `backend/app/routers/export.py`
  - CSV / Excel / JSON exports
- `backend/app/routers/scheduler.py`
  - cron read/update
- `backend/app/routers/system_config.py`
  - spring display cutoff
- `backend/app/routers/company_recrawl.py`
  - company recrawl queue
- `backend/app/routers/job_intel.py`
  - job intel tasks, records, summary, platform bootstrap

### Services
- Crawl family:
  - `backend/app/services/crawler.py`
  - `backend/app/services/haitou_crawler.py`
  - `backend/app/services/moka_crawler.py`
  - `backend/app/services/securities_crawler.py`
  - `backend/app/services/securities_playwright_crawler.py`
  - `backend/app/services/energy_crawler.py`
  - `backend/app/services/bank_crawler/`
  - `backend/app/services/legacy_crawlers/`
- Cross-cutting services:
  - scoring, export, scheduler, seed, system_config
  - crawl detection/evidence/validation/taxonomy/runtime helpers
  - company recrawl queue + site recrawl helpers
- Job intel:
  - orchestrator, normalizer, ranker, snapshot builder, query builder
  - platform adapters live under `backend/app/services/platform_intel/adapters/`

### Models, schemas, database
- `backend/app/models.py` contains the canonical ORM models.
- `backend/app/schemas.py` and `backend/app/schemas_job_intel.py` contain API payloads.
- `backend/app/database.py` creates the SQLAlchemy engine/session.
- Canonical DB path in code is `backend/data/jobradar.db`.

## Frontend Architecture

### App shell and routing
- `frontend/src/App.tsx` wires the main navigation and route-level pages.
- The app is a page-heavy SPA; most behavior lives inside page components.

### Pages
- `frontend/src/pages/Jobs.tsx` main job list, filters, export/import, status updates
- `frontend/src/pages/CompanyExpand.tsx` company/department drill-down and recrawl entry
- `frontend/src/pages/Crawl.tsx` crawl trigger, logs, recrawl queue
- `frontend/src/pages/Tracks.tsx` track/group/keyword editing
- `frontend/src/pages/Scoring.tsx` raw scoring config editor and rescore
- `frontend/src/pages/Exclude.tsx` exclude rules and spring display toggle
- `frontend/src/pages/Scheduler.tsx` cron schedule editing
- `frontend/src/pages/JobIntel.tsx` job intel task flow and records

### Shared frontend utilities
- `frontend/src/api/index.ts` is the single API client entry.
- `frontend/src/utils/time.ts` contains time formatting helpers.
- `frontend/src/components/intel/` holds reusable intel UI pieces, but the page currently does most of the orchestration.

## Major User Flows

### Job browsing
- User opens the job table, filters by search/track/date/status/score, and exports or imports data.
- Backend computes weighted scores from `job_scores` + `tracks`.

### Crawl and recrawl
- User triggers crawl from the UI.
- Backend runs crawl logic, stores logs, and rescoring may run after new data lands.
- Company recrawl queues feed back into normalized jobs.

### Track and scoring management
- User edits tracks, groups, keywords, and scoring config.
- User can trigger a full rescore after config changes.

### Scheduler and display rules
- APScheduler controls the daily/cron-driven crawl cycle.
- Spring display cutoff filters visible jobs across views and exports.

### Job intel enrichment
- User triggers an intel task for a job.
- The backend builds a task, runs platform adapters, stores records and snapshots, and exposes the result through the UI.

## Stable vs Evolving Areas

### Stable
- jobs list/filter/export/import
- tracks/scoring/exclude/scheduler/system config
- core crawl families and crawler diagnostics

### Evolving / MVP-ish
- job intel multi-platform coverage
- some recrawl heuristics
- page-level refactors and intel component reuse

## Change Impact Guide
- `models.py` changes can affect DB, schemas, routers, and frontend payloads.
- `frontend/src/api/index.ts` changes can affect many pages at once.
- `backend/app/main.py` changes can alter startup, seeding, middleware, and SPA serving.
- `backend/app/services/crawler.py` changes can affect crawl logs, scoring, and recrawl behavior.
- `backend/app/services/system_config.py` changes can affect listing and export visibility.

## Read Next
- Rules and commands: `AGENTS.md`
- Deployment and data boundaries: `docs/deployment-and-data.md`
