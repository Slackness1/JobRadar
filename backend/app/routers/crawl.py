import asyncio
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models import CrawlLog
from app.schemas import CrawlLogOut, CrawlStatusOut, CrawlTriggerOut
from app.services.crawler import get_token, run_crawl
from app.services.scorer import score_all_jobs

router = APIRouter(prefix="/api/crawl", tags=["crawl"])

_crawl_running = False


@router.post("/trigger", response_model=CrawlTriggerOut)
async def trigger_crawl():
    global _crawl_running
    if _crawl_running:
        return CrawlTriggerOut(log_id=0, message="Crawl already in progress")

    _crawl_running = True

    def _run():
        global _crawl_running
        try:
            token = ""
            token_error = ""
            try:
                token = asyncio.run(get_token(headless=True)) or ""
            except Exception as exc:
                token_error = str(exc)

            db = SessionLocal()
            log = run_crawl(db, token=token)
            if token_error:
                existing = getattr(log, "error_message", "")
                combined = f"{existing}; Tata token error: {token_error}" if existing else f"Tata token error: {token_error}"
                setattr(log, "error_message", combined[:500])
                db.commit()
                db.refresh(log)
            log_new_count = int(getattr(log, "new_count", 0) or 0)
            if log_new_count > 0:
                score_all_jobs(db)
            log_id = int(getattr(log, "id", 0) or 0)
            db.close()
            return log_id
        finally:
            _crawl_running = False

    log_id = await asyncio.to_thread(_run)
    return CrawlTriggerOut(log_id=log_id, message="Crawl started")


@router.get("/status", response_model=CrawlStatusOut)
def crawl_status(db: Session = Depends(get_db)):
    latest = db.query(CrawlLog).order_by(CrawlLog.id.desc()).first()
    is_running = _crawl_running
    log_out = CrawlLogOut.model_validate(latest) if latest else None
    return CrawlStatusOut(is_running=is_running, current_log=log_out)


@router.get("/logs", response_model=list[CrawlLogOut])
def crawl_logs(db: Session = Depends(get_db)):
    logs = db.query(CrawlLog).order_by(CrawlLog.id.desc()).limit(50).all()
    return logs
