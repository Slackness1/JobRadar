import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.database import engine, SessionLocal, Base
from app import models  # noqa: F401
from app.models import CrawlLog
from app.services.company_recrawl_queue import mark_stale_running_tasks_failed
from app.services.seed import seed_from_yaml
from app.services.schema_patch import ensure_compatible_schema
from app.services.scheduler_service import start_scheduler

from app.routers import tracks, scoring, exclude, jobs, crawl, export, scheduler, system_config, company_recrawl


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables + seed + scheduler
    Base.metadata.create_all(bind=engine)
    ensure_compatible_schema(engine)
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

        mark_stale_running_tasks_failed(db)

        seeded = seed_from_yaml(db)
        if seeded:
            print("[INFO] Seeded database from config.yaml")
    finally:
        db.close()
    start_scheduler()
    print("[INFO] Scheduler started")
    yield


app = FastAPI(title="JobRadar API", lifespan=lifespan)

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
