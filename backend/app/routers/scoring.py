import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models import ScoringConfig
from app.schemas import ScoringConfigOut, ScoringConfigIn
from app.services.scorer import score_all_jobs

router = APIRouter(prefix="/api/scoring", tags=["scoring"])

_rescore_running = False


@router.get("/config", response_model=ScoringConfigOut)
def get_config(db: Session = Depends(get_db)):
    cfg = db.query(ScoringConfig).first()
    if not cfg:
        raise HTTPException(404, "No scoring config found")
    return cfg


@router.put("/config", response_model=ScoringConfigOut)
def update_config(data: ScoringConfigIn, db: Session = Depends(get_db)):
    cfg = db.query(ScoringConfig).first()
    if not cfg:
        cfg = ScoringConfig(config_json=data.config_json)
        db.add(cfg)
    else:
        cfg.config_json = data.config_json
        cfg.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(cfg)
    return cfg


@router.post("/rescore")
async def rescore():
    global _rescore_running
    if _rescore_running:
        return {"message": "Rescore already in progress"}
    _rescore_running = True

    def _run():
        global _rescore_running
        try:
            db = SessionLocal()
            count = score_all_jobs(db)
            db.close()
            return count
        finally:
            _rescore_running = False

    count = await asyncio.to_thread(_run)
    return {"message": f"Rescored {count} job-track pairs"}
