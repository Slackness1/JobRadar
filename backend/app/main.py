import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import models  # noqa: F401  # 确保模型被导入以参与建表
from app.database import Base, SessionLocal, engine
from app.middleware.readonly_guest import ReadOnlyGuestMiddleware
from app.models import CrawlLog
from app.routers import (
    company_recrawl,
    crawl,
    exclude,
    export,
    interview,
    job_intel,
    jobs,
    resume_copilot,
    scheduler,
    scoring,
    sites,
    system_config,
    tracks,
)
from app.services.company_recrawl_queue import mark_stale_running_tasks_failed
from app.services.resume_copilot.demo_session import ensure_demo_session
from app.services.schema_patch import ensure_compatible_schema
from app.services.scheduler_service import start_scheduler
from app.services.seed import seed_from_yaml


def _run_alembic_upgrade() -> None:
    from alembic import command
    from alembic.config import Config

    backend_dir = Path(__file__).resolve().parent.parent
    cfg_path = backend_dir / 'alembic.ini'
    if not cfg_path.exists():
        return
    cfg = Config(str(cfg_path))
    cfg.set_main_option('script_location', str(backend_dir / 'alembic'))
    command.upgrade(cfg, 'head')
    print('[INFO] alembic upgrade head OK')


def _check_playwright_browsers() -> None:
    # Best-effort: surface missing Chromium at boot instead of 09:00 tier-crawl.
    # Incident 2026-05-07: cache wiped during VPS migration; only noticed 19h
    # later when BrowserType.launch failed inside the daily cron.
    try:
        import json
        import playwright
        pw_dir = Path(playwright.__file__).parent
        browsers_json = pw_dir / 'driver' / 'package' / 'browsers.json'
        cache_dir = Path.home() / '.cache' / 'ms-playwright'
        if not browsers_json.exists():
            return
        data = json.loads(browsers_json.read_text())
        for b in data.get('browsers', []):
            if b.get('name') == 'chromium-headless-shell' and b.get('installByDefault'):
                expected = cache_dir / f"chromium_headless_shell-{b['revision']}"
                if not expected.is_dir():
                    print(
                        f'[ERROR] Playwright Chromium headless shell missing at {expected} '
                        f'— run: <venv>/bin/playwright install chromium',
                        flush=True,
                    )
                    return
        print('[INFO] Playwright browsers OK', flush=True)
    except Exception as exc:
        print(f'[WARN] Playwright browser check skipped: {exc}', flush=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables + schema patch + seed + scheduler
    Base.metadata.create_all(bind=engine)
    ensure_compatible_schema(engine)
    _run_alembic_upgrade()
    _check_playwright_browsers()

    db = SessionLocal()
    try:
        stale_logs = db.query(CrawlLog).filter(CrawlLog.status == "running").all()
        if stale_logs:
            for log in stale_logs:
                setattr(log, "status", "failed")
                setattr(log, "finished_at", datetime.utcnow())
                existing = getattr(log, "error_message", "")
                if not existing:
                    setattr(log, "error_message", "Interrupted by service restart")
            db.commit()

        # 同样清理 company_crawl_logs 子表的 orphan running 行。Phase 5 故障
        # 调查发现 2448 中铁特货物流 行 stuck "running" 4 天没人清，导致后续
        # tier-crawl 写入争锁失败。
        from app.models import CompanyCrawlLog  # local import to avoid circular
        stale_company_logs = db.query(CompanyCrawlLog).filter(CompanyCrawlLog.status == "running").all()
        if stale_company_logs:
            for log in stale_company_logs:
                setattr(log, "status", "failed")
                setattr(log, "finished_at", datetime.utcnow())
                existing = getattr(log, "error_message", "") or ""
                if not existing:
                    setattr(log, "error_message", "Interrupted by service restart")
            db.commit()
            print(f"[INFO] Cleaned {len(stale_company_logs)} stale company_crawl_logs orphans")

        mark_stale_running_tasks_failed(db)

        seeded = seed_from_yaml(db)
        if seeded:
            print("[INFO] Seeded database from config.yaml")

        try:
            ensure_demo_session(db)
            print("[INFO] Demo session ready (id=1)")
        except Exception as exc:  # demo seeding must not block startup
            print(f"[WARN] ensure_demo_session failed: {exc}")
    finally:
        db.close()

    start_scheduler()
    print("[INFO] Scheduler started")
    yield


app = FastAPI(title="JobRadar API", lifespan=lifespan)

# Add read-only guest middleware (must be added before CORS middleware)
app.add_middleware(ReadOnlyGuestMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routers
app.include_router(jobs.router)
app.include_router(tracks.router)
app.include_router(scoring.router)
app.include_router(exclude.router)
app.include_router(crawl.router)
app.include_router(export.router)
app.include_router(scheduler.router)
app.include_router(system_config.router)
app.include_router(company_recrawl.router)
app.include_router(job_intel.router)
app.include_router(resume_copilot.router)
app.include_router(interview.router)
app.include_router(sites.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Serve frontend static files in production
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = FRONTEND_DIST / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIST / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
