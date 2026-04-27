"""APScheduler for daily crawl + rescore."""
import asyncio
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.database import SessionLocal
from app.services.crawler import get_token, run_crawl
from app.services.guest_cleanup import cleanup_expired_guest_records
from app.services.interview.nowcoder.refresh_job import (
    get_last_refresh_status as get_nowcoder_status,
    run_refresh as run_nowcoder_refresh,
)
from app.services.scorer import score_all_jobs

scheduler = BackgroundScheduler()
SCHEDULER_TZ = ZoneInfo("Asia/Shanghai")

DEFAULT_CRON = "0 8 * * *"
_current_cron = DEFAULT_CRON

JOB_ID = "daily_crawl"
GUEST_CLEANUP_JOB_ID = "guest_cleanup"
NOWCODER_INTEL_JOB_ID = "nowcoder_intel_refresh"
NOWCODER_INTEL_CRON = "0 */3 * * *"  # every 3h, 8 runs/day, accumulate over time


def _daily_crawl_job():
    try:
        try:
            token = asyncio.run(get_token(headless=True)) or ""
        except Exception:
            token = ""
        db = SessionLocal()
        log = run_crawl(db, token=token)
        new_count = int(getattr(log, "new_count", 0) or 0)
        if new_count > 0:
            score_all_jobs(db)
        db.close()
    except Exception as e:
        print(f"[SCHEDULER ERROR] {e}")


def _nowcoder_intel_job():
    db = SessionLocal()
    try:
        run_nowcoder_refresh(db)
    except Exception as e:
        print(f"[NOWCODER INTEL ERROR] {e}")
    finally:
        db.close()


def _guest_cleanup_job():
    try:
        result = cleanup_expired_guest_records()
        if result['sessions_removed'] or result['reports_removed']:
            print(
                f"[GUEST CLEANUP] removed {result['sessions_removed']} sessions, "
                f"{result['reports_removed']} interview reports"
            )
    except Exception as e:
        print(f"[GUEST CLEANUP ERROR] {e}")


def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(
            _daily_crawl_job,
            CronTrigger.from_crontab(DEFAULT_CRON, timezone=SCHEDULER_TZ),
            id=JOB_ID,
            replace_existing=True,
        )
        scheduler.add_job(
            _guest_cleanup_job,
            IntervalTrigger(hours=1),
            id=GUEST_CLEANUP_JOB_ID,
            replace_existing=True,
        )
        scheduler.add_job(
            _nowcoder_intel_job,
            CronTrigger.from_crontab(NOWCODER_INTEL_CRON, timezone=SCHEDULER_TZ),
            id=NOWCODER_INTEL_JOB_ID,
            replace_existing=True,
        )
        scheduler.start()


def update_cron(cron_expr: str):
    global _current_cron
    _current_cron = cron_expr
    scheduler.reschedule_job(JOB_ID, trigger=CronTrigger.from_crontab(cron_expr, timezone=SCHEDULER_TZ))


def get_scheduler_info() -> dict:
    job = scheduler.get_job(JOB_ID)
    next_run = None
    if job is not None:
        next_run_time = getattr(job, "next_run_time", None)
        if next_run_time is not None:
            next_run = next_run_time.isoformat()

    nowcoder_job = scheduler.get_job(NOWCODER_INTEL_JOB_ID)
    nowcoder_next_run = None
    if nowcoder_job is not None:
        nrt = getattr(nowcoder_job, "next_run_time", None)
        if nrt is not None:
            nowcoder_next_run = nrt.isoformat()

    nowcoder_status = get_nowcoder_status()
    nowcoder_status["cron_expression"] = NOWCODER_INTEL_CRON
    nowcoder_status["next_run"] = nowcoder_next_run

    return {
        "cron_expression": _current_cron,
        "next_run": next_run,
        "is_active": scheduler.running,
        "nowcoder_intel_refresh": nowcoder_status,
    }
