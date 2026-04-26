from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models import CompanyCrawlLog, CrawlLog
from app.schemas_sites import (
    SiteRecrawlOut,
    SiteRowOut,
    SiteRunOut,
    SitesSummaryOut,
)
from app.services.company_crawler_registry import COMPANY_CRAWLERS, recrawl_company
from app.services.scorer import score_all_jobs
from app.services.sites_alert import alert_level


router = APIRouter(prefix="/api/sites", tags=["sites"])


def _shanghai_today_start() -> datetime:
    """Return today 00:00 Asia/Shanghai expressed as naive UTC."""
    sh = timezone(timedelta(hours=8))
    now_sh = datetime.now(sh)
    today_sh = now_sh.replace(hour=0, minute=0, second=0, microsecond=0)
    return today_sh.astimezone(timezone.utc).replace(tzinfo=None)


def _build_site_rows(db: Session, source_filter: Optional[str]) -> list[SiteRowOut]:
    q = db.query(
        CompanyCrawlLog.company,
        CompanyCrawlLog.source,
    )
    if source_filter:
        q = q.filter(CompanyCrawlLog.source == source_filter)
    pairs = q.distinct().all()

    today_start = _shanghai_today_start()
    rows: list[SiteRowOut] = []
    now = datetime.utcnow()
    for company, source in pairs:
        runs = (
            db.query(CompanyCrawlLog)
            .filter(CompanyCrawlLog.company == company, CompanyCrawlLog.source == source)
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
        rows.append(SiteRowOut(
            company=company,
            source=source,
            last_run_at=last.started_at if last else None,
            last_status=last.status if last else None,
            today_new=int(today_new or 0),
            last_error_short=(last.error_message[:120] if last and last.error_message else ""),
            alert_level=alert_level(runs, now),
        ))
    return rows


@router.get("/summary", response_model=SitesSummaryOut)
def get_summary(db: Session = Depends(get_db)) -> SitesSummaryOut:
    rows = _build_site_rows(db, None)
    active = sum(1 for r in rows if r.alert_level == "green")
    alerted = sum(1 for r in rows if r.alert_level in ("yellow", "red"))
    disabled = len(set(COMPANY_CRAWLERS.keys()) - {r.company for r in rows})
    total_today_new = sum(r.today_new for r in rows)

    last_batch = (
        db.query(CrawlLog)
        .order_by(CrawlLog.id.desc())
        .first()
    )
    return SitesSummaryOut(
        active=active,
        alerted=alerted,
        disabled=disabled,
        total_today_new=total_today_new,
        last_batch_at=last_batch.started_at if last_batch else None,
        last_batch_status=last_batch.status if last_batch else None,
    )


@router.get("", response_model=list[SiteRowOut])
def list_sites(
    source: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> list[SiteRowOut]:
    return _build_site_rows(db, source)


@router.get("/{company}/runs", response_model=list[SiteRunOut])
def get_company_runs(
    company: str,
    limit: int = Query(24, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[SiteRunOut]:
    runs = (
        db.query(CompanyCrawlLog)
        .filter(CompanyCrawlLog.company == company)
        .order_by(CompanyCrawlLog.started_at.desc())
        .limit(limit)
        .all()
    )
    return [SiteRunOut.model_validate(r) for r in runs]


def _run_recrawl_in_background(company: str, parent_log_id: int) -> None:
    db = SessionLocal()
    try:
        recrawl_company(db=db, company=company, parent_log_id=parent_log_id)
        new_total = (
            db.query(func.coalesce(func.sum(CompanyCrawlLog.new_count), 0))
            .filter(CompanyCrawlLog.parent_log_id == parent_log_id)
            .scalar()
        )
        if int(new_total or 0) > 0:
            score_all_jobs(db)
        parent = db.query(CrawlLog).filter(CrawlLog.id == parent_log_id).first()
        if parent is not None:
            parent.status = "success"
            parent.finished_at = datetime.utcnow()
            parent.new_count = int(new_total or 0)
            db.commit()
    except Exception as exc:
        parent = db.query(CrawlLog).filter(CrawlLog.id == parent_log_id).first()
        if parent is not None:
            parent.status = "failed"
            parent.finished_at = datetime.utcnow()
            parent.error_message = str(exc)[:500]
            db.commit()
    finally:
        db.close()


@router.post("/{company}/recrawl", response_model=SiteRecrawlOut)
def recrawl_company_endpoint(
    company: str,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
) -> SiteRecrawlOut:
    if company not in COMPANY_CRAWLERS:
        raise HTTPException(status_code=400, detail=f"未配置 {company} 的爬虫")

    parent = CrawlLog(
        source=f"recrawl:{company}",
        started_at=datetime.utcnow(),
        status="running",
    )
    db.add(parent)
    db.commit()
    db.refresh(parent)

    background.add_task(_run_recrawl_in_background, company, parent.id)
    return SiteRecrawlOut(parent_log_id=parent.id, message="已启动")
