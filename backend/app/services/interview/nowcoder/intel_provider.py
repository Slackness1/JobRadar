from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.models import InterviewIntelKeyword


@dataclass(slots=True, frozen=True)
class IntelView:
    keyword: str
    summary_md: str
    source_count: int


def get_intel_for_target_job(db: Session, target_job: str) -> Optional[IntelView]:
    if not target_job:
        return None
    target = target_job.strip()
    if not target:
        return None
    try:
        rows = db.query(InterviewIntelKeyword).all()
    except Exception:
        return None

    # Pass 1: exact match
    for row in rows:
        if row.keyword == target and (row.summary_md or "").strip():
            return IntelView(keyword=row.keyword, summary_md=row.summary_md, source_count=row.source_count or 0)

    # Pass 2: substring match (longest keyword wins)
    candidates = [row for row in rows if row.keyword and row.keyword in target and (row.summary_md or "").strip()]
    if not candidates:
        return None
    best = max(candidates, key=lambda r: len(r.keyword))
    return IntelView(keyword=best.keyword, summary_md=best.summary_md, source_count=best.source_count or 0)
