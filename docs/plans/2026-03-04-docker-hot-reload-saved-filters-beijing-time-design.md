# Design: Docker Hot Reload + Saved Filters + Beijing Time

Date: 2026-03-04
Scope: JobRadar web app (frontend + backend + docker)

## 1) Goals

- Enable development-time hot reload in Docker without affecting production compose.
- Allow users to save filter settings in Job Overview and apply them with one click.
- Make crawl management and scheduler times display and compute in Beijing time (Asia/Shanghai).

## 2) Non-Goals

- No cross-device sync for saved filters in this iteration.
- No DB schema changes for saved filter presets.
- No breaking changes to existing production `docker-compose.yml` runtime behavior.

## 3) Requirements Summary

- Development mode uses a dedicated compose file and source mounts.
- Frontend supports save/apply/delete preset filters and restores last-used filter state.
- Crawl and scheduler time shown in UI as Beijing time.
- Scheduler trigger semantics use Beijing timezone so next-run is correct.

## 4) Approach Options and Decision

### Option A (Chosen)

- Add `docker-compose.dev.yml` for development only.
- Keep production compose unchanged.
- Save filters in browser `localStorage`.
- Use `Intl.DateTimeFormat` with `Asia/Shanghai` in frontend display.
- Set `CronTrigger` timezone to `Asia/Shanghai` in backend scheduler.

Pros: Lowest risk, fastest delivery, no migration.
Cons: Saved presets are per-browser only.

### Option B

- One compose with profile toggles for dev/prod.

Pros: Fewer files.
Cons: Easier to misconfigure production with development flags.

### Option C

- Save filter presets on server side (new table + APIs).

Pros: Cross-device and multi-user ready.
Cons: Larger change set and higher complexity for current need.

## 5) Detailed Design

### 5.1 Docker Hot Reload (Dev Only)

New file: `docker-compose.dev.yml`

- `backend`:
  - command: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
  - bind mount: `./backend:/app/backend`
  - env_file: `.env`
  - port mapping: `8001:8000` (avoid local 8000 conflicts)
- `frontend`:
  - dev server: `npm run dev -- --host 0.0.0.0 --port 5173`
  - bind mount: `./frontend:/app`
  - named volume for `/app/node_modules`
  - port mapping: `5173:5173`
- Frontend dev proxy target should resolve docker service name:
  - in docker dev: `/api -> http://backend:8000`

### 5.2 Saved Filters in Job Overview

File: `frontend/src/pages/Jobs.tsx`

- Persisted schema (localStorage key: `jobradar.savedFilters.v1`):
  - `id: string`
  - `name: string`
  - `search: string`
  - `trackFilter?: string`
  - `days?: number`
  - `minScore?: number`
  - `createdAt: string`
- Last applied state key: `jobradar.lastFilterState.v1`

UI actions:

- Save current filter (with name prompt/modal)
- Apply saved filter from dropdown (one click)
- Delete selected saved filter
- Auto-restore last-used filter on first load

Behavior:

- Applying preset sets all filter states and triggers list refresh.
- Duplicate name save prompts overwrite behavior.
- Invalid/corrupted localStorage data falls back to empty preset list safely.

### 5.3 Beijing Time Display and Scheduler Timezone

Frontend files:

- `frontend/src/pages/Crawl.tsx`
- `frontend/src/pages/Scheduler.tsx`

Display rule:

- Replace direct `new Date(...).toLocaleString('zh-CN')` with formatter using:
  - locale: `zh-CN`
  - timezone: `Asia/Shanghai`

Backend file:

- `backend/app/services/scheduler_service.py`

Scheduler rule:

- Build and reschedule cron trigger with `timezone='Asia/Shanghai'`.
- Return `next_run` as ISO datetime string from timezone-aware datetime.

## 6) Error Handling

- localStorage parsing failures: catch and reset to defaults.
- missing/invalid datetime string in UI: display `-`.
- overwrite conflict on same preset name: explicit user confirmation.
- port conflict in dev mode: default to 8001 backend and 5173 frontend.

## 7) Testing and Verification Plan

- Frontend lint/typecheck passes.
- Backend imports and API start pass.
- Docker dev mode:
  - modify a frontend TSX file -> browser reflects changes without rebuild.
  - modify a backend router/service file -> API reloads automatically.
- Job Overview:
  - save preset, refresh page, apply in one click, delete preset.
- Time validation:
  - Crawl page start times show CST (UTC+8).
  - Scheduler next-run aligns with configured Beijing cron expectation.

## 8) Rollout Notes

- Production run command remains existing `docker compose up --build -d`.
- Development run command becomes:
  - `docker compose -f docker-compose.dev.yml up --build`

## 9) Risks and Mitigations

- Risk: frontend proxy mismatch between local and docker dev.
  - Mitigation: document dev-proxy host strategy; keep production unaffected.
- Risk: user confusion between prod and dev compose files.
  - Mitigation: README section with explicit commands and expected ports.
