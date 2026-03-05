# Docker Hot Reload + Saved Filters + Beijing Time Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add dev-only Docker hot reload, saved one-click filters in Job Overview, and Beijing-time-correct time display/scheduling.

**Architecture:** Keep production compose untouched and introduce a dedicated development compose file with bind mounts and reload commands. Implement filter persistence fully on frontend using localStorage and explicit save/apply/delete actions. Normalize timezone handling by enforcing `Asia/Shanghai` in frontend formatters and APScheduler cron trigger timezone in backend.

**Tech Stack:** Docker Compose, FastAPI, Uvicorn, APScheduler, React, TypeScript, Ant Design, Vite.

---

### Task 1: Add Development Docker Compose for Hot Reload

**Files:**
- Create: `docker-compose.dev.yml`
- Modify: `frontend/vite.config.ts`
- Modify: `README.md`

**Step 1: Write the failing check**

Run:

```bash
docker compose -f docker-compose.dev.yml config
```

Expected: fail because `docker-compose.dev.yml` does not exist yet.

**Step 2: Create minimal dev compose**

Create `docker-compose.dev.yml` with:
- `backend` service using `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
- bind mount `./backend:/app/backend`
- env file `.env`
- port `8001:8000`
- `frontend` service using `npm run dev -- --host 0.0.0.0 --port 5173`
- bind mount `./frontend:/app`
- named volume mount `/app/node_modules`
- port `5173:5173`

**Step 3: Update Vite proxy target for container networking**

In `frontend/vite.config.ts`, set `/api` proxy target to `http://backend:8000` when running inside docker dev (keep simple deterministic target for this project).

**Step 4: Verify compose syntax and startup**

Run:

```bash
docker compose -f docker-compose.dev.yml config
docker compose -f docker-compose.dev.yml up --build -d
docker compose -f docker-compose.dev.yml ps
```

Expected:
- `config` succeeds
- both services show `Up`

**Step 5: Verify hot reload behavior**

Run:

```bash
docker compose -f docker-compose.dev.yml logs --tail=100 frontend backend
```

Then edit one line in:
- `frontend/src/pages/Jobs.tsx`
- `backend/app/routers/jobs.py`

Expected:
- frontend HMR log appears
- backend `--reload` restart log appears

**Step 6: Document dev run commands**

Add README section:
- dev start: `docker compose -f docker-compose.dev.yml up --build`
- prod start: existing `docker compose up --build -d`
- expected ports (`5173`, `8001`)

---

### Task 2: Add Saved Filter Presets and One-Click Apply in Job Overview

**Files:**
- Modify: `frontend/src/pages/Jobs.tsx`
- (Optional helper) Create: `frontend/src/utils/filters.ts`

**Step 1: Write the failing check (manual)**

Current behavior check:
- open Job Overview
- set filters
- refresh page

Expected (before change): filters are lost; no saved preset actions exist.

**Step 2: Add persisted data model and storage helpers**

In `Jobs.tsx` add types and constants:
- `SavedFilterPreset`
- `SAVED_FILTERS_KEY = 'jobradar.savedFilters.v1'`
- `LAST_FILTER_KEY = 'jobradar.lastFilterState.v1'`

Add safe helpers with `try/catch`:
- load presets
- save presets
- load last filter
- save last filter

**Step 3: Add UI actions**

In filter toolbar add buttons/selectors:
- save current filter
- apply saved filter (one click)
- delete selected saved filter

Use Ant Design components already in project style (`Button`, `Select`, `message`, optional `Modal`).

**Step 4: Wire one-click apply and restore logic**

- applying preset sets `search`, `trackFilter`, `days`, `minScore`, resets page to 1
- save last used filter whenever filters change
- restore last used filter on first render before first fetch

**Step 5: Add overwrite/delete edge handling**

- on same-name save: confirm overwrite
- on malformed localStorage data: fallback to empty array
- on deleting currently selected preset: clear selection and keep UI stable

**Step 6: Verify behavior end-to-end**

Manual checks:
- save preset -> appears in list
- refresh -> presets remain
- click apply preset -> list updates instantly
- delete preset -> removed and no runtime error

---

### Task 3: Enforce Beijing Time Display in Crawl and Scheduler UI

**Files:**
- Modify: `frontend/src/pages/Crawl.tsx`
- Modify: `frontend/src/pages/Scheduler.tsx`
- (Optional helper) Create: `frontend/src/utils/time.ts`

**Step 1: Write the failing check (manual)**

Open pages and compare displayed times with known Beijing time; current output depends on browser/system timezone.

**Step 2: Implement shared formatter**

Create formatter utility (or inline function) using:

```ts
new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit', second: '2-digit',
  hour12: false,
})
```

Function returns `-` for empty/invalid input.

**Step 3: Replace page usages**

- `Crawl.tsx`: replace `new Date(v).toLocaleString('zh-CN')`
- `Scheduler.tsx`: replace `new Date(nextRun).toLocaleString('zh-CN')`

**Step 4: Verify display**

Manual check:
- both pages show consistent CST/Beijing outputs regardless of host timezone
- invalid/null values render `-`

---

### Task 4: Set Backend Scheduler to Beijing Timezone

**Files:**
- Modify: `backend/app/services/scheduler_service.py`

**Step 1: Write the failing check**

Run scheduler info endpoint and inspect `next_run` under non-UTC+8 host settings; it can drift from expected Beijing schedule.

**Step 2: Add timezone-aware trigger creation**

In scheduler service:
- define timezone constant for `Asia/Shanghai`
- use it in `CronTrigger.from_crontab(..., timezone=...)` for initial add and reschedule

**Step 3: Normalize next_run serialization**

Return `next_run` as ISO string from timezone-aware datetime (`job.next_run_time.isoformat()`).

**Step 4: Verify endpoint behavior**

Run:

```bash
curl http://localhost:8001/api/scheduler
```

Expected:
- `next_run` contains timezone offset or tz-aware ISO string consistent with Beijing schedule.

---

### Task 5: Validation, Regression, and Docs Finalization

**Files:**
- Modify: `README.md`
- Verify changed files:
  - `docker-compose.dev.yml`
  - `frontend/vite.config.ts`
  - `frontend/src/pages/Jobs.tsx`
  - `frontend/src/pages/Crawl.tsx`
  - `frontend/src/pages/Scheduler.tsx`
  - `backend/app/services/scheduler_service.py`

**Step 1: Run frontend checks**

Run:

```bash
docker compose -f docker-compose.dev.yml exec frontend npm run build
```

Expected: build succeeds.

**Step 2: Run backend startup check**

Run:

```bash
docker compose -f docker-compose.dev.yml logs --tail=200 backend
```

Expected: app starts without traceback.

**Step 3: Run smoke API checks**

Run:

```bash
curl -I http://localhost:5173
curl -I http://localhost:8001/api/jobs
curl -I http://localhost:8001/api/scheduler
```

Expected: HTTP responses returned (2xx/3xx acceptable for index endpoints).

**Step 4: Run functional checklist**

- frontend hot update works
- backend hot reload works
- save/apply/delete presets works
- crawl and scheduler pages show Beijing time
- scheduler next-run aligns with Beijing cron

**Step 5: Update docs section and troubleshooting**

In README add:
- dev/prod command split
- ports and conflict tips
- note that saved filters are browser-local for now

---

## Dependencies and Ordering

- Task 1 first (dev runtime foundation).
- Task 2 and Task 3 can run in parallel after Task 1.
- Task 4 depends only on backend and can run parallel with Task 2/3.
- Task 5 after all implementation tasks.

## Risk Controls

- Keep production compose unchanged.
- Use defensive localStorage parsing.
- Enforce explicit timezone (`Asia/Shanghai`) both in frontend formatter and backend cron trigger.
- Validate with both runtime logs and endpoint smoke checks.
