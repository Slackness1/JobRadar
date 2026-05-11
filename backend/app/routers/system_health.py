"""System health overview.

Aggregates scheduler + crawler + db + recent-events data into a single payload
for the /system-health admin page (absorbs /sites).

This endpoint is fast and read-only — meant for dashboard polling every ~30s.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CompanyCrawlLog, CrawlLog, Job, ResumeCopilotSession
from app.services.company_crawler_registry import COMPANY_CRAWLERS
from app.services.scheduler_service import get_scheduler_info
from app.services.sites_alert import alert_level


router = APIRouter(prefix="/api/system-health", tags=["system-health"])


def _shanghai_now() -> datetime:
    sh = timezone(timedelta(hours=8))
    return datetime.now(sh).replace(tzinfo=None)


def _shanghai_today_start() -> datetime:
    sh = timezone(timedelta(hours=8))
    now_sh = datetime.now(sh)
    today_sh = now_sh.replace(hour=0, minute=0, second=0, microsecond=0)
    return today_sh.astimezone(timezone.utc).replace(tzinfo=None)


def _db_file_stats() -> dict:
    db_path = Path(__file__).resolve().parent.parent.parent / "data" / "jobradar.db"
    if not db_path.exists():
        return {"path": str(db_path), "size_bytes": 0, "size_mb": 0.0}
    sz = db_path.stat().st_size
    return {
        "path": str(db_path),
        "size_bytes": sz,
        "size_mb": round(sz / (1024 * 1024), 2),
    }


def _services_block(db: Session, sched: dict) -> list[dict]:
    """Translate raw status snapshots into UI-ready service tiles."""
    today_start = _shanghai_today_start()

    # APScheduler — count enabled jobs
    sched_jobs = sched.get("jobs") or []
    sched_active = sched.get("is_active", False)

    # Crawler health — count failed companies in last 24h
    cutoff = datetime.utcnow() - timedelta(hours=24)
    crawler_failed = (
        db.query(func.count(CompanyCrawlLog.id))
        .filter(
            CompanyCrawlLog.started_at >= cutoff,
            CompanyCrawlLog.status == "failed",
        )
        .scalar()
        or 0
    )
    crawler_ok = (
        db.query(func.count(CompanyCrawlLog.id))
        .filter(
            CompanyCrawlLog.started_at >= cutoff,
            CompanyCrawlLog.status == "success",
        )
        .scalar()
        or 0
    )
    crawler_stat = "ok" if crawler_failed == 0 else ("warn" if crawler_failed < 5 else "down")

    # Jobs table size
    jobs_total = db.query(func.count(Job.id)).scalar() or 0
    jobs_today = (
        db.query(func.count(Job.id))
        .filter(Job.created_at >= today_start)
        .scalar()
        or 0
    )

    # Resume copilot sessions today
    rc_today = (
        db.query(func.count(ResumeCopilotSession.id))
        .filter(ResumeCopilotSession.created_at >= today_start)
        .scalar()
        or 0
    )

    # DB file
    db_stats = _db_file_stats()

    return [
        {
            "name": "Web · uvicorn",
            "sub": "FastAPI · single worker",
            "status": "ok",
            "metric": f"jobs {jobs_total}",
        },
        {
            "name": "SQLite (WAL)",
            "sub": "jobradar.db",
            "status": "ok",
            "metric": f"{db_stats['size_mb']} MB",
        },
        {
            "name": "APScheduler",
            "sub": f"{len(sched_jobs)} jobs",
            "status": "ok" if sched_active else "down",
            "metric": "active" if sched_active else "stopped",
        },
        {
            "name": f"爬虫节点 ×{len(COMPANY_CRAWLERS)}",
            "sub": f"24h 成功 {crawler_ok} · 失败 {crawler_failed}",
            "status": crawler_stat,
            "metric": f"+{jobs_today} 新岗位",
        },
        {
            "name": "Resume Copilot",
            "sub": "DeepSeek · 简历助手",
            "status": "ok",
            "metric": f"今日 {rc_today} 会话",
        },
        {
            "name": "Sentry",
            "sub": "错误监控",
            "status": "ok" if not os.environ.get("SENTRY_DOWN") else "warn",
            "metric": "—",
        },
    ]


def _sites_block(db: Session) -> dict:
    """Per-company crawler state — used to render the embedded /sites list."""
    pairs = db.query(CompanyCrawlLog.company, CompanyCrawlLog.source).distinct().all()
    today_start = _shanghai_today_start()
    rows: list[dict] = []
    now = datetime.utcnow()
    alert_counts = {"green": 0, "yellow": 0, "red": 0, "unknown": 0}
    for company, source in pairs:
        runs = (
            db.query(CompanyCrawlLog)
            .filter(
                CompanyCrawlLog.company == company,
                CompanyCrawlLog.source == source,
            )
            .order_by(CompanyCrawlLog.started_at.desc())
            .limit(10)
            .all()
        )
        today_new = (
            db.query(func.coalesce(func.sum(CompanyCrawlLog.new_count), 0))
            .filter(
                CompanyCrawlLog.company == company,
                CompanyCrawlLog.source == source,
                CompanyCrawlLog.started_at >= today_start,
            )
            .scalar()
        )
        last = runs[0] if runs else None
        lvl = alert_level(runs, now)
        alert_counts[lvl] = alert_counts.get(lvl, 0) + 1
        rows.append({
            "company": company,
            "source": source,
            "last_run_at": last.started_at.isoformat() if last and last.started_at else None,
            "last_status": last.status if last else None,
            "today_new": int(today_new or 0),
            "alert_level": lvl,
            "last_error_short": (last.error_message[:120] if last and last.error_message else ""),
        })
    rows.sort(key=lambda r: (
        # red first, then yellow, then green
        {"red": 0, "yellow": 1, "unknown": 2, "green": 3}.get(r["alert_level"], 4),
        -(r["today_new"] or 0),
    ))
    return {"rows": rows, "alert_counts": alert_counts}


def _recent_events(db: Session) -> list[dict]:
    """Most recent crawler failures + the latest batch logs."""
    out: list[dict] = []
    cutoff = datetime.utcnow() - timedelta(days=7)
    failed = (
        db.query(CompanyCrawlLog)
        .filter(
            CompanyCrawlLog.started_at >= cutoff,
            CompanyCrawlLog.status == "failed",
        )
        .order_by(CompanyCrawlLog.started_at.desc())
        .limit(8)
        .all()
    )
    for f in failed:
        out.append({
            "severity": "warn",
            "title": f"{f.company} {f.source} 爬虫失败",
            "when": f.started_at.isoformat() if f.started_at else "",
            "who": (f.error_message or "")[:120],
        })

    batches = (
        db.query(CrawlLog)
        .filter(CrawlLog.started_at >= cutoff)
        .order_by(CrawlLog.started_at.desc())
        .limit(8)
        .all()
    )
    for b in batches:
        sev = "ok" if b.status == "success" else ("warn" if b.status == "failed" else "info")
        new_cnt = getattr(b, "new_count", None)
        title_extra = f" · +{new_cnt} 新" if new_cnt else ""
        out.append({
            "severity": sev,
            "title": f"批次 {b.source}{title_extra}",
            "when": b.started_at.isoformat() if b.started_at else "",
            "who": (b.status or "") + (" · " + (b.error_message or "")[:80] if b.error_message else ""),
        })

    # Sort merged list by 'when' descending
    out.sort(key=lambda x: x.get("when", ""), reverse=True)
    return out[:12]


@router.get("")
def get_system_health(db: Session = Depends(get_db)) -> dict:
    sched = get_scheduler_info()
    services = _services_block(db, sched)
    sites = _sites_block(db)
    events = _recent_events(db)

    today_start = _shanghai_today_start()
    today_new_total = sum(r["today_new"] for r in sites["rows"])

    # Last batch summary
    last_batch = (
        db.query(CrawlLog)
        .order_by(CrawlLog.id.desc())
        .first()
    )

    return {
        "headline": {
            "overall": "ok" if not any(s["status"] in ("warn", "down") for s in services) else "warn",
            "today_new": today_new_total,
            "alert_red": sites["alert_counts"].get("red", 0),
            "alert_yellow": sites["alert_counts"].get("yellow", 0),
            "alert_green": sites["alert_counts"].get("green", 0),
            "last_batch_at": last_batch.started_at.isoformat() if last_batch and last_batch.started_at else None,
            "last_batch_status": last_batch.status if last_batch else None,
            "generated_at": datetime.utcnow().isoformat() + "Z",
        },
        "services": services,
        "scheduler": {
            "is_active": sched.get("is_active", False),
            "next_run": sched.get("next_run"),
            "jobs": sched.get("jobs", []),
        },
        "sites": sites["rows"],
        "events": events,
    }
