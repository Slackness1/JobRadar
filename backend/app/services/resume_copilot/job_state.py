"""岗位级用户状态领域逻辑(推荐 2.0)。

纯 DB upsert + 集合查询,不含 HTTP / LLM。每个调用方自己持有 Session。
state 互斥规则与设计稿 2026-06-16 §3.1 一致。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import JobUserState

STATE_SEEN = "seen"
STATE_SAVED = "saved"
STATE_APPLIED = "applied"
STATE_DISMISSED = "dismissed"
EXPLICIT_STATES = {STATE_SAVED, STATE_APPLIED, STATE_DISMISSED}
ALL_STATES = EXPLICIT_STATES | {STATE_SEEN}


def _rows(db: Session, user_key: str):
    return db.query(JobUserState).filter(JobUserState.user_key == user_key)


def states_map(db: Session, user_key: str) -> dict[str, str]:
    return {r.job_id: r.state for r in _rows(db, user_key)}


def seen_or_dismissed_ids(db: Session, user_key: str) -> set[str]:
    """轮换排除集 = 该用户已有任何状态行的全部 job_id(出现过即不再算"新")。"""
    return {r.job_id for r in _rows(db, user_key)}


def mark_seen(db: Session, user_key: str, job_ids, source_session_id=None) -> int:
    """对没有任何状态行的 job_id 插 seen;已有行(任何状态)保持不动。返回新增数。"""
    if not user_key or not job_ids:
        return 0
    existing = {r.job_id for r in _rows(db, user_key).filter(JobUserState.job_id.in_(list(job_ids)))}
    now = datetime.utcnow()
    n = 0
    for jid in job_ids:
        jid = str(jid)
        if jid in existing:
            continue
        db.add(JobUserState(
            user_key=user_key, job_id=jid, state=STATE_SEEN,
            first_seen_at=now, state_updated_at=now, source_session_id=source_session_id,
            created_at=now, updated_at=now,
        ))
        existing.add(jid)
        n += 1
    db.commit()
    return n


def set_explicit_state(db: Session, user_key: str, job_id: str, state: str, source_session_id=None) -> JobUserState:
    if state not in EXPLICIT_STATES:
        raise ValueError(f"state must be one of {sorted(EXPLICIT_STATES)}, got {state!r}")
    job_id = str(job_id)
    now = datetime.utcnow()
    row = _rows(db, user_key).filter(JobUserState.job_id == job_id).first()
    if row is None:
        row = JobUserState(
            user_key=user_key, job_id=job_id, state=state,
            first_seen_at=now, source_session_id=source_session_id, created_at=now,
        )
        db.add(row)
    else:
        row.state = state
    row.state_updated_at = now
    row.updated_at = now
    db.commit()
    db.refresh(row)
    return row


def my_jobs_grouped(db: Session, user_key: str) -> dict:
    """按显式状态分组,join jobs 取展示字段。seen 不进任何组。

    返回 {saved:[...], applied:[...], dismissed:[...], counts:{...}}。
    每个 item:{job_id, company, job_title, location, detail_url, publish_date, scraped_at}。
    """
    from app.models import Job  # 局部 import 避免循环

    rows = [r for r in _rows(db, user_key) if r.state in EXPLICIT_STATES]
    job_ids = [r.job_id for r in rows]
    jobs = {j.job_id: j for j in db.query(Job).filter(Job.job_id.in_(job_ids))} if job_ids else {}
    groups: dict[str, list] = {STATE_SAVED: [], STATE_APPLIED: [], STATE_DISMISSED: []}
    for r in sorted(rows, key=lambda x: (x.state_updated_at or x.created_at), reverse=True):
        j = jobs.get(r.job_id)
        groups[r.state].append({
            "job_id": r.job_id,
            "company": getattr(j, "company", "") or "",
            "job_title": getattr(j, "job_title", "") or "",
            "location": getattr(j, "location", "") or "",
            "detail_url": getattr(j, "detail_url", "") or "",
            "publish_date": (j.publish_date.isoformat() if j and j.publish_date else ""),
            "scraped_at": (j.scraped_at.isoformat() if j and j.scraped_at else ""),
        })
    return {**groups, "counts": {k: len(v) for k, v in groups.items()}}


def clear_explicit_state(db: Session, user_key: str, job_id: str) -> None:
    """显式状态降回 seen(保留行 → 仍算看过)。无行则无操作。"""
    row = _rows(db, user_key).filter(JobUserState.job_id == str(job_id)).first()
    if row is None:
        return
    row.state = STATE_SEEN
    row.state_updated_at = datetime.utcnow()
    row.updated_at = datetime.utcnow()
    db.commit()
