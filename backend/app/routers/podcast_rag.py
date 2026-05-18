"""Podcast knowledge-base RAG endpoints.

GET /api/podcasts/search    semantic + filter search
GET /api/podcasts/stats     debug counts
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.podcasts import retrieve

router = APIRouter(prefix="/api/podcasts", tags=["podcasts"])


def _split(s: str | None) -> list[str]:
    return [x.strip() for x in (s or "").split(",") if x.strip()]


@router.get("/search")
def search(
    q: str | None = Query(default=None, description="Semantic query text"),
    type: str | None = Query(default=None, description="Comma-separated insight types"),
    role: str | None = Query(default=None, description="Comma-separated canonical role names"),
    company: str | None = Query(default=None, description="Comma-separated canonical company names"),
    sector: str | None = Query(default=None, description="Comma-separated canonical sector names"),
    min_confidence: str | None = Query(default=None, description="Min confidence: high|med|low"),
    eid: str | None = Query(default=None, description="Restrict to a single episode eid"),
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    return {
        "results": retrieve.search(
            db,
            query=q,
            types=_split(type),
            role=_split(role),
            company=_split(company),
            sector=_split(sector),
            min_confidence=min_confidence,
            eid=eid,
            limit=limit,
        ),
    }


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    return retrieve.stats(db)


@router.post("/reload")
def reload_cache(db: Session = Depends(get_db)):
    """Force-reload the in-memory embedding cache. Call after re-running ingest."""
    n = retrieve.reload_cache(db)
    return {"reloaded": True, "n_insights": n}
