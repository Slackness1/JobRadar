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
TIER_CRAWL_JOB_ID = "daily_tier_crawl"
DEFAULT_TIER_CRON = "0 9 * * *"
DIGEST_JOB_ID = "daily_digest"
DEFAULT_DIGEST_CRON = "35 9 * * *"
LINK_PROBE_JOB_ID = "daily_link_probe"
DEFAULT_LINK_PROBE_CRON = "0 10 * * *"  # 10:00 Asia/Shanghai, after tier crawl + digest


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
        try:
            from app.services.job_hygiene import dedup_jobs
            print(f"[HYGIENE][daily] {dedup_jobs(db)}")
        except Exception as he:
            print(f"[HYGIENE ERROR][daily] {he}")
        db.close()
    except Exception as e:
        print(f"[SCHEDULER ERROR] {e}")


def _nowcoder_intel_job():
    try:
        run_nowcoder_refresh()
    except Exception as e:
        print(f"[NOWCODER INTEL ERROR] {e}")


def _daily_tier_crawl_job():
    """Cron job at 09:00 Asia/Shanghai. Runs all 4 tier orchestrators
    sequentially with error isolation per tier. Populates company_crawl_logs
    automatically. Re-scores once at the end if any new jobs were added.
    """
    import traceback as _tb
    from datetime import datetime
    from app.models import CrawlLog, Job

    db = SessionLocal()
    try:
        # Create a parent CrawlLog so per-company rows can FK link via parent_log_id
        parent = CrawlLog(
            source="tier-crawl",
            started_at=datetime.utcnow(),
            status="running",
        )
        db.add(parent)
        db.commit()
        db.refresh(parent)
        parent_id = parent.id

        total_new = 0
        errors = []

        # Each tier wrapped so one failure doesn't stop the others.
        # The orchestrators write per-company rows via company_crawl_log.

        try:
            from app.services.internet_crawler import (
                build_internet_targets,
                crawl_internet_targets,
                select_primary_targets,
            )
            targets = select_primary_targets(build_internet_targets())
            results = crawl_internet_targets(db, targets, parent_log_id=parent_id)
            total_new += sum(getattr(r, "new_count", 0) or 0 for r in results)
        except Exception as exc:
            errors.append(f"internet: {exc}")
            _tb.print_exc()
            print(f"[TIER CRAWL ERROR][internet] {exc}")

        try:
            from app.services.state_owned_crawler import (
                build_state_owned_targets,
                crawl_state_owned_targets,
            )
            targets = build_state_owned_targets()
            results = crawl_state_owned_targets(db, targets, parent_log_id=parent_id)
            total_new += sum(getattr(r, "new_count", 0) or 0 for r in results)
        except Exception as exc:
            errors.append(f"state_owned: {exc}")
            _tb.print_exc()
            print(f"[TIER CRAWL ERROR][state_owned] {exc}")

        try:
            from app.services.securities_crawler import run_configured_securities_crawl
            existing = {j.job_id: j for j in db.query(Job).all() if j.job_id}
            new_count, _total, _per_company = run_configured_securities_crawl(
                db, existing, parent_log_id=parent_id
            )
            total_new += int(new_count or 0)
        except Exception as exc:
            errors.append(f"securities: {exc}")
            _tb.print_exc()
            print(f"[TIER CRAWL ERROR][securities] {exc}")

        try:
            from app.services.consumer_foreign_crawler import (
                build_consumer_targets,
                crawl_consumer_targets,
                select_primary_targets,
            )
            targets = select_primary_targets(build_consumer_targets())
            results = crawl_consumer_targets(db, targets, parent_log_id=parent_id)
            total_new += sum(getattr(r, "new_count", 0) or 0 for r in results)
        except Exception as exc:
            errors.append(f"consumer_foreign: {exc}")
            _tb.print_exc()
            print(f"[TIER CRAWL ERROR][consumer_foreign] {exc}")

        try:
            from app.services.bank_tier_crawler import crawl_banks
            new_count = crawl_banks(db, parent_log_id=parent_id)
            total_new += int(new_count or 0)
        except Exception as exc:
            errors.append(f"banks: {exc}")
            _tb.print_exc()
            print(f"[TIER CRAWL ERROR][banks] {exc}")

        # Phase 6 — 金融扩展
        try:
            from app.services.insurance_tier_crawler import crawl_insurers
            new_count = crawl_insurers(db, parent_log_id=parent_id)
            total_new += int(new_count or 0)
        except Exception as exc:
            errors.append(f"insurance: {exc}")
            _tb.print_exc()
            print(f"[TIER CRAWL ERROR][insurance] {exc}")

        try:
            from app.services.funds_crawler import run_configured_funds_crawl
            existing = {j.job_id: j for j in db.query(Job).all() if j.job_id}
            new_count, _, _ = run_configured_funds_crawl(db, existing, parent_log_id=parent_id)
            total_new += int(new_count or 0)
        except Exception as exc:
            errors.append(f"funds: {exc}")
            _tb.print_exc()
            print(f"[TIER CRAWL ERROR][funds] {exc}")

        # Phase 7 wave-3 — PE/VC (源码资本/鼎晖/黑石/KKR)
        try:
            from app.services.pe_vc_tier_crawler import crawl_pe_vc
            new_count = crawl_pe_vc(db, parent_log_id=parent_id)
            total_new += int(new_count or 0)
        except Exception as exc:
            errors.append(f"pe_vc: {exc}")
            _tb.print_exc()
            print(f"[TIER CRAWL ERROR][pe_vc] {exc}")

        # Phase 9 — 头部私募 (幻方/九坤/高毅/衍复)
        try:
            from app.services.hedge_funds_tier_crawler import crawl_hedge_funds
            new_count, _, _ = crawl_hedge_funds(db, parent_log_id=parent_id)
            total_new += int(new_count or 0)
        except Exception as exc:
            errors.append(f"hedge_funds: {exc}")
            _tb.print_exc()
            print(f"[TIER CRAWL ERROR][hedge_funds] {exc}")

        # Phase 10 — 外资投行 (Citi / Morgan Stanley)
        try:
            from app.services.foreign_ibs_tier_crawler import crawl_foreign_ibs
            new_count, _, _ = crawl_foreign_ibs(db, parent_log_id=parent_id)
            total_new += int(new_count or 0)
        except Exception as exc:
            errors.append(f"foreign_ibs: {exc}")
            _tb.print_exc()
            print(f"[TIER CRAWL ERROR][foreign_ibs] {exc}")

        # Phase 13 — 消费外企 Workday 补充（阿斯利康等）
        try:
            from app.services.consumer_foreign_workday_crawler import crawl_consumer_foreign_workday
            new_count, _, _ = crawl_consumer_foreign_workday(db, parent_log_id=parent_id)
            total_new += int(new_count or 0)
        except Exception as exc:
            errors.append(f"consumer_foreign_workday: {exc}")
            _tb.print_exc()
            print(f"[TIER CRAWL ERROR][consumer_foreign_workday] {exc}")

        # Phase 14 — 清华就业网匿名公开金融岗 (高瓴/信银理财/Cayuga/源乐晟 等无 ATS 的)
        try:
            from app.services.thu_career_crawler import crawl_thu_career_finance
            existing = {j.job_id: j for j in db.query(Job).all() if j.job_id}
            new_count, _, _ = crawl_thu_career_finance(db, existing_jobs=existing, parent_log_id=parent_id)
            total_new += int(new_count or 0)
        except Exception as exc:
            errors.append(f"thu_career: {exc}")
            _tb.print_exc()
            print(f"[TIER CRAWL ERROR][thu_career] {exc}")

        # Finalize parent
        parent.finished_at = datetime.utcnow()
        parent.status = "failed" if errors else "success"
        parent.new_count = total_new
        if errors:
            parent.error_message = "; ".join(errors)[:500]
        db.commit()

        if total_new > 0:
            score_all_jobs(db)
        try:
            from app.services.job_hygiene import dedup_jobs
            print(f"[HYGIENE][tier] {dedup_jobs(db)}")
        except Exception as he:
            _tb.print_exc()
            print(f"[HYGIENE ERROR][tier] {he}")
    except Exception as exc:
        _tb.print_exc()
        print(f"[TIER CRAWL ERROR][outer] {exc}")
    finally:
        db.close()


def _daily_digest_job():
    from app.config import CRAWLER_LLM_DIGEST_ENABLED
    if not CRAWLER_LLM_DIGEST_ENABLED:
        return
    db = SessionLocal()
    try:
        from datetime import datetime as _dt
        from app.services.crawler_llm_digest import (
            aggregate_today_stats,
            generate_daily_digest,
            persist_digest,
        )
        stats = aggregate_today_stats(db, _dt.utcnow())
        if stats["total_companies"] == 0:
            return
        text = generate_daily_digest(stats)
        if text:
            persist_digest(db, text)
    except Exception as exc:
        print(f"[DIGEST ERROR] {exc}")
    finally:
        db.close()


def _daily_link_probe_job():
    """L3: HEAD detail_url on L1+L2 candidate pool, mark dead links."""
    db = SessionLocal()
    try:
        from app.services.link_prober import probe_active_jobs
        stats = probe_active_jobs(db, workers=50)
        print(
            f"[LINK PROBE] total={stats['total']} alive={stats['alive']} dead={stats['dead']} "
            f"skipped={stats['skipped']} unchanged={stats['unchanged']} "
            f"elapsed={stats.get('elapsed_seconds', 0):.1f}s"
        )
    except Exception as exc:
        print(f"[LINK PROBE ERROR] {exc}")
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
            _daily_tier_crawl_job,
            CronTrigger.from_crontab(DEFAULT_TIER_CRON, timezone=SCHEDULER_TZ),
            id=TIER_CRAWL_JOB_ID,
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        scheduler.add_job(
            _daily_digest_job,
            CronTrigger.from_crontab(DEFAULT_DIGEST_CRON, timezone=SCHEDULER_TZ),
            id=DIGEST_JOB_ID,
            replace_existing=True,
            coalesce=True,
            max_instances=1,
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
        scheduler.add_job(
            _daily_link_probe_job,
            CronTrigger.from_crontab(DEFAULT_LINK_PROBE_CRON, timezone=SCHEDULER_TZ),
            id=LINK_PROBE_JOB_ID,
            replace_existing=True,
            coalesce=True,
            max_instances=1,
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

    job_cron_map = {
        JOB_ID: _current_cron,
        TIER_CRAWL_JOB_ID: DEFAULT_TIER_CRON,
        DIGEST_JOB_ID: DEFAULT_DIGEST_CRON,
        NOWCODER_INTEL_JOB_ID: NOWCODER_INTEL_CRON,
        GUEST_CLEANUP_JOB_ID: "interval:1h",
    }
    jobs_out: list[dict] = []
    for j in scheduler.get_jobs():
        nrt = getattr(j, "next_run_time", None)
        jobs_out.append(
            {
                "id": j.id,
                "cron_expression": job_cron_map.get(j.id, str(j.trigger)),
                "next_run": nrt.isoformat() if nrt is not None else None,
            }
        )

    return {
        "cron_expression": _current_cron,
        "next_run": next_run,
        "is_active": scheduler.running,
        "nowcoder_intel_refresh": nowcoder_status,
        "jobs": jobs_out,
    }
