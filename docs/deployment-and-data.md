# JobRadar Deployment And Data

## Purpose
- This document defines the boundaries between local development, VPS production, and runtime data.
- Use it when changing deployment, database, auth/session state, or data import/export behavior.

## Canonical Truth Box
- **VPS is the source of truth for production data.**
- Local WSL2 is for development and verification.
- Deploy code from Git; do not overwrite production data files from local by default.
- Canonical database path in code is `backend/data/jobradar.db`.
- `backend/data/jobs.db` appears in older docs/env files but should be treated as legacy unless a migration explicitly says otherwise.

## Environment Modes

### Local WSL2 development
- Default mode for feature work, tests, and frontend/backend integration.
- Use local data only for development validation.

### Optional shadow runtime
- Use only when you need isolation from an already running environment.
- Shadow runtime is disposable/snapshot-like and should not be treated as prod truth.

### VPS production
- Tencent Cloud VPS hosts the real public service.
- Production should be treated as a separate runtime with its own persistent state.

## Current Runtime Model
- Checked-in dev compose is local-first and not a production contract.
- Current compose shape:
  - backend on host `8001` in Docker dev
  - frontend on host `5173`
  - API proxy via `/api`
- Frontend code uses relative `/api` requests, so production must keep proxying or same-origin routing intact.

## Recommended Production Shape
- Frontend: build `frontend/dist/` and let nginx serve static assets.
- Backend: run `uvicorn` under `systemd` on `127.0.0.1:8000`.
- Nginx: terminate TLS, serve the SPA, and proxy `/api` to the backend.
- Suggested domains:
  - `jobcopilot.top` for the frontend
  - `api.jobcopilot.top` for the backend API

## Deployment Flow
1. Develop locally in WSL2.
2. Validate with backend tests, frontend lint, and frontend build.
3. Push code to Git.
4. On VPS, pull the target commit or tag.
5. Build the frontend on the VPS or deploy a prepared build artifact.
6. Restart backend/systemd and reload nginx.
7. Run a health check on `/api/health` and a simple frontend request.

## Code vs Data Boundaries

### Version-controlled
- `backend/app/`
- `frontend/src/`
- `backend/config/`
- `docs/`
- `scripts/`
- `config.yaml`

### Runtime-only / never overwrite casually
- `.env`
- `backend/data/jobradar.db`
- `backend/data/browser_sessions/`
- `backend/data/auth/`
- export files, crawl outputs, backups, validation reports

### Importable / transferrable data
- curated CSVs
- curated JSON snapshots
- truth-layer outputs
- other explicit import artifacts created for a deployment step

## Database And Persistence Rules
- SQLite is the active persistence layer in current code.
- Startup may create tables, patch schema, seed from config, and start the scheduler.
- Do not deploy by copying a local DB file over the VPS DB unless the operation is explicitly a migration/restore.
- If schema changes are involved, back up the VPS DB first.

## Runtime Data Directories
- `backend/data/jobradar.db` is the main live DB.
- `backend/data/browser_sessions/` stores browser session state for some platform-intel flows.
- `backend/data/auth/` stores auth-like runtime state when used.
- `data/exports/` and related artifact directories contain generated outputs.

## Safe Update Strategy
- Publish code separately from data.
- Treat database/data-file updates as an explicit second step, not part of ordinary deploys.
- Use import scripts or API endpoints for new data instead of replacing the whole DB.
- Keep backups for the production DB and any runtime state before a schema or crawler change.

## Known Inconsistencies To Watch
- Older docs and `.env` references may still mention `jobs.db`.
- The app code currently points to `jobradar.db`.
- Some docs describe production via nginx + systemd, while checked-in dev compose still uses hot-reload dev servers.
- Resolve these by checking the code and this document first, not by guessing from stale files.

## Operational Rules For Agents
- Never assume local WSL2 state is prod state.
- Never overwrite production DB/auth/session files during a code deploy.
- Never conflate code publishing with data migration.
- Before changing deployment, verify the actual VPS path, service manager, and domain mapping.

## Read Next
- System structure and module map: `docs/architecture.md`
- Repo rules and commands: `AGENTS.md`
