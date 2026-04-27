import time
import threading
import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator, Optional

from sqlalchemy.orm import Session

from app.config import CRAWLER_LLM_DIAGNOSE_ENABLED
from app.models import CompanyCrawlLog

logger = logging.getLogger(__name__)

_ERROR_TRUNCATE = 500


def _schedule_diagnosis_async(log_id: int, company: str, source: str, error_message: str) -> None:
    """Dispatch a non-blocking diagnosis. Best-effort, swallowed on any failure."""
    if not CRAWLER_LLM_DIAGNOSE_ENABLED:
        return

    def _worker() -> None:
        try:
            from app.database import SessionLocal
            from app.services.crawler_llm_diagnose import diagnose_failure
            from sqlalchemy import desc

            db_local = SessionLocal()
            try:
                # Pull 5 most recent successful runs for same company
                successes_q = (
                    db_local.query(CompanyCrawlLog)
                    .filter(
                        CompanyCrawlLog.company == company,
                        CompanyCrawlLog.status == "success",
                    )
                    .order_by(desc(CompanyCrawlLog.started_at))
                    .limit(5)
                    .all()
                )
                successes = [
                    {
                        "started_at": s.started_at.isoformat() if s.started_at else "",
                        "fetched_count": s.fetched_count,
                        "new_count": s.new_count,
                        "duration_ms": s.duration_ms,
                    }
                    for s in successes_q
                ]

                # Best-effort: read the legacy crawler source for the company
                crawler_code = _read_crawler_source_for(company)

                suggestion = diagnose_failure(
                    company=company,
                    source=source,
                    error_message=error_message,
                    recent_successes=successes,
                    crawler_code=crawler_code,
                )
                if suggestion:
                    row = db_local.query(CompanyCrawlLog).filter(CompanyCrawlLog.id == log_id).first()
                    if row is not None:
                        row.suggested_fix = suggestion[:2000]
                        db_local.commit()
            finally:
                db_local.close()
        except Exception as exc:  # noqa: BLE001
            logger.debug("diagnosis worker failed: %s", exc)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


# Mapping company → legacy-crawler function name (best-effort).
# Add entries as needed; missing entries fall back to empty source.
_COMPANY_FUNC_HINTS: dict[str, str] = {
    "腾讯": "crawl_tencent",
    "阿里巴巴": "crawl_alibaba",
    "蚂蚁集团": "crawl_antgroup",
    "字节跳动": "crawl_bytedance",
    "美团": "crawl_meituan",
    "京东": "crawl_jd",
    "快手": "crawl_kuaishou",
    "拼多多": "crawl_pdd",
    "百度": "crawl_baidu",
    "网易": "crawl_163",
    "网易雷火": "crawl_leihuo",
    "哔哩哔哩": "crawl_bilibili",
    "米哈游": "crawl_mihoyo",
    "携程": "crawl_ctrip",
    "得物": "crawl_dewu",
    "BOSS直聘": "crawl_boss_campus",
}


def _read_crawler_source_for(company: str) -> str:
    """Best-effort: extract the source of the legacy crawler function for this company."""
    fn_name = _COMPANY_FUNC_HINTS.get(company)
    if not fn_name:
        return ""
    try:
        from pathlib import Path
        path = Path(__file__).resolve().parent / "legacy_crawlers" / "crawler.py"
        if not path.exists():
            return ""
        text = path.read_text(encoding="utf-8")
        marker = f"def {fn_name}("
        idx = text.find(marker)
        if idx < 0:
            return ""
        # Take from the def to the next blank line followed by `def ` (rough heuristic)
        snippet = text[idx : idx + 8000]
        # Trim at next top-level def
        lines = snippet.split("\n")
        result_lines = [lines[0]]
        for line in lines[1:]:
            if line.startswith("def ") and result_lines:
                break
            result_lines.append(line)
        return "\n".join(result_lines)
    except Exception:
        return ""


@contextmanager
def company_crawl_log(
    db: Session,
    *,
    source: str,
    company: str,
    parent_log_id: Optional[int],
) -> Iterator[CompanyCrawlLog]:
    log = CompanyCrawlLog(
        source=source,
        company=company,
        parent_log_id=parent_log_id,
        started_at=datetime.utcnow(),
        status="running",
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    start = time.monotonic()
    try:
        yield log
        log.status = "success"
    except Exception as exc:
        log.status = "failed"
        log.error_message = str(exc)[:_ERROR_TRUNCATE]
        # Schedule background diagnosis BEFORE re-raising. Capture id to avoid
        # holding session across thread boundary.
        try:
            log_id = int(getattr(log, "id", 0) or 0)
            err_str = str(exc)[:_ERROR_TRUNCATE]
            if log_id:
                # Commit current state so the worker can re-query a stable row.
                db.commit()
                _schedule_diagnosis_async(log_id, company, source, err_str)
        except Exception:  # noqa: BLE001
            pass
        raise
    finally:
        log.finished_at = datetime.utcnow()
        log.duration_ms = int((time.monotonic() - start) * 1000)
        db.commit()
