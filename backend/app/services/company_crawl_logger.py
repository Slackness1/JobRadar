import time
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator, Optional

from sqlalchemy.orm import Session

from app.models import CompanyCrawlLog

_ERROR_TRUNCATE = 500


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
        raise
    finally:
        log.finished_at = datetime.utcnow()
        log.duration_ms = int((time.monotonic() - start) * 1000)
        db.commit()
