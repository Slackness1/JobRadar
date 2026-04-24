# Resume Copilot Sync Status

Last updated: 2026-04-15

## Local Debug Entry Points

- Main project directory: `/home/chuanbo/projects/JobRadar`
- Resume Copilot feature worktree: `/home/chuanbo/projects/JobRadar/.worktrees/resume-copilot-mvp`
- Claude-style public frontend now copied into main project directory: `/home/chuanbo/projects/JobRadar/resume-copilot-web`
- Resume Copilot backend API and services now copied into main project directory under `backend/app/`

## Synced Into Main Project Directory

These files were synced from the `feat/resume-copilot-mvp` worktree into `/home/chuanbo/projects/JobRadar` for local debugging and future conversation handoff:

- `resume-copilot-web/`
- `backend/app/routers/resume_copilot.py`
- `backend/app/schemas_resume_copilot.py`
- `backend/app/services/resume_copilot/`
- `backend/app/config.py`
- `backend/app/main.py`
- `backend/app/models.py`
- `backend/app/routers/__init__.py`
- `backend/app/services/schema_patch.py`
- `backend/requirements.txt`
- `backend/tests/test_resume_copilot_router.py`
- `backend/tests/test_resume_feedback_service.py`
- `backend/tests/test_resume_parser_service.py`
- `backend/tests/test_resume_recommendation_service.py`

Generated frontend/backend artifacts were intentionally not synced:

- `resume-copilot-web/node_modules/`
- `resume-copilot-web/.next/`
- Python `__pycache__/` and `*.pyc`

## Previously Synced To `main`

Company tier and crawler tooling was already synced to local/GitHub `main` in commit:

- `9784952 feat(crawlers): sync sector tier tooling from wip branch`

That includes:

- `backend/scripts/annotate_job_company_tiers.py`
- `backend/scripts/run_internet_tier_crawl.py`
- `backend/scripts/run_consulting_tier_crawl.py`
- `backend/scripts/run_consumer_foreign_tier_crawl.py`
- `backend/scripts/run_securities_research_tier_crawl.py`
- `backend/scripts/run_state_owned_tier_crawl.py`
- `backend/config/tiered_internet_companies.yaml`
- `backend/config/tiered_consumer_companies.yaml`
- `backend/config/consulting_campus.yaml`
- `backend/config/consulting_firms.yaml`
- `data/exports/company_truth_spring_master.csv`
- `data/exports/job_truth_spring_master.csv`

## Previously Synced To VPS

The VPS repo at `/home/ubuntu/opencode-worktrees/jobrador-edit` was moved to `main` commit `9784952`.

The VPS live database was annotated in place with company tier labels using:

- `/home/ubuntu/opencode-worktrees/jobrador-edit/backend/scripts/annotate_job_company_tiers.py`

The VPS backend was restarted and health-checked after annotation.

## Not Yet Committed

The Claude-style Resume Copilot frontend and Resume Copilot backend workflow code are currently synced into the local main project directory as working-tree changes, but they have not yet been committed to `main`.

## Current Local Runtime

The main project directory can run the synced version with:

- Backend: `cd /home/chuanbo/projects/JobRadar/backend && PYTHONPATH=. .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8002`
- Frontend: `cd /home/chuanbo/projects/JobRadar/resume-copilot-web && RESUME_COPILOT_BACKEND_URL=http://127.0.0.1:8002 npm run dev -- --hostname 127.0.0.1`

The current main-directory SQLite database does not contain the previous worktree-only `sessionId=15`; upload a new resume from the main-directory runtime to test the synced path.
