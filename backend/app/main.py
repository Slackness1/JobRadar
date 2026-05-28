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
from app.middleware.llm_quota_context import LlmQuotaContextMiddleware
from app.models import CrawlLog
from app.routers import (
    company_recrawl,
    coverage,
    crawl,
    exclude,
    export,
    intel_enrichment,
    interview,
    job_intel,
    jobs,
    podcast_rag,
    recommend_v2,
    resume_copilot,
    review_queue,
    scheduler,
    scoring,
    sites,
    student_kb,
    system_config,
    system_health,
    teacher_entry,
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

    # Register pluggable LLM context providers (podcast / future memory / future tencent…).
    try:
        from app.services.llm_context import bootstrap as bootstrap_llm_context, registered_names
        bootstrap_llm_context()
        print(f"[INFO] LLM context providers: {registered_names()}")
    except Exception as exc:
        print(f"[WARN] llm_context bootstrap failed: {exc}")

    yield


app = FastAPI(title="JobRadar API", lifespan=lifespan)


# Access-log middleware (2026-05-21 #4) — uvicorn 自带 access log 在 dev
# 跑久了会被各种因素吃掉(stdout 缓冲 / log config 漂移),  debug 时彻底瞎。
# 这里加一道显式 ASGI middleware 写 method/path/status/elapsed_ms 一行,
# 异常单独捕获 + 打 traceback 到同一个 logger。
import logging as _stdlib_logging
import sys as _stdlib_sys
import time as _stdlib_time
import traceback as _stdlib_traceback


def _ensure_access_logger() -> _stdlib_logging.Logger:
    """uvicorn 的 access log 默认在 dev 跑久了会消失 (stdout 缓冲 / 配置漂移)。
    显式给 jobradar.access 挂一个 stderr handler, 一次性的, 防重复挂。
    """
    logger = _stdlib_logging.getLogger("jobradar.access")
    if any(getattr(h, "_jobradar_access_marker", False) for h in logger.handlers):
        return logger
    handler = _stdlib_logging.StreamHandler(_stdlib_sys.stderr)
    handler.setLevel(_stdlib_logging.INFO)
    handler.setFormatter(
        _stdlib_logging.Formatter('[%(levelname)s] %(asctime)s %(message)s', '%H:%M:%S')
    )
    handler._jobradar_access_marker = True  # type: ignore[attr-defined]
    logger.addHandler(handler)
    logger.setLevel(_stdlib_logging.INFO)
    logger.propagate = False
    return logger


_access_logger = _ensure_access_logger()


@app.middleware("http")
async def _access_log_middleware(request, call_next):
    start = _stdlib_time.monotonic()
    try:
        response = await call_next(request)
    except Exception as exc:  # noqa: BLE001 — last-mile catch for visibility
        elapsed_ms = int((_stdlib_time.monotonic() - start) * 1000)
        msg = (
            f"[ERROR] {request.method} {request.url.path} → EXCEPTION ({elapsed_ms}ms) "
            f"{type(exc).__name__}\n{_stdlib_traceback.format_exc()}"
        )
        print(msg, file=_stdlib_sys.stderr, flush=True)
        raise
    elapsed_ms = int((_stdlib_time.monotonic() - start) * 1000)
    status_code = getattr(response, "status_code", 0)
    # 5xx / 4xx 标 ERROR / WARN 让眼一扫就看见
    level = (
        _stdlib_logging.ERROR if status_code >= 500
        else _stdlib_logging.WARNING if status_code >= 400
        else _stdlib_logging.INFO
    )
    # 直接 print 绕开 logging 配置漂移问题 — uvicorn dev 跑久了, custom logger
    # 的 handler 时不时被吃掉 (gunicorn worker reload / uvicorn fileobj 重定向
    # 重置); print(flush=True) 反而是最稳的兜底。
    level_tag = (
        "ERROR" if status_code >= 500
        else "WARN" if status_code >= 400
        else "INFO"
    )
    print(
        f"[{level_tag}] {request.method} {request.url.path} → {status_code} ({elapsed_ms}ms)",
        file=_stdlib_sys.stderr,
        flush=True,
    )
    _ = level  # 保留变量以防之后切回 logger 路径
    return response


# Add read-only guest middleware (must be added before CORS middleware)
app.add_middleware(ReadOnlyGuestMiddleware)
app.add_middleware(LlmQuotaContextMiddleware)

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
app.include_router(coverage.router)
app.include_router(teacher_entry.router)
app.include_router(review_queue.router)
app.include_router(system_health.router)
app.include_router(podcast_rag.router)
app.include_router(student_kb.router)
app.include_router(intel_enrichment.router)
app.include_router(recommend_v2.router)

from app.routers import auth as _auth_router  # noqa: E402
app.include_router(_auth_router.router)


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
