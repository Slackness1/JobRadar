"""Student personal-knowledge-base API.

Keyed on X-Resume-User-Key header — same auth model as resume-copilot session
endpoints. Guest/demo user_keys are blocked at write time inside the extractor;
read endpoints reject them at the request edge.

The shape mirrors Claude Code's memory file system:
- GET /index          → MEMORY.md equivalent (always-on summary list, no body)
- GET /experiences    → individual memory files (filterable by category/dimension)
- POST /confirm       → user manually validates a low-confidence candidate
- PATCH /experience   → user edits summary/hook (audit raw_excerpt stays put)
- POST /archive       → user marks superseded (LLM stops surfacing in interview)
- DELETE              → user removes outright (KB is the user's data, they own deletion)
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import StudentExperience


router = APIRouter(prefix='/api/student-kb', tags=['student-kb'])


_RESERVED_USER_KEYS = {'__demo__', '__guest__', ''}


# ---------- schemas ----------------------------------------------------------


class ExperienceIndexItem(BaseModel):
    """One row of the always-on summary index — MEMORY.md-equivalent."""

    id: int
    summary: str
    category: str
    star_dimensions: list[str]
    confidence: float
    user_confirmed: bool
    captured_at: datetime
    age_days: int


class ExperienceDetail(BaseModel):
    id: int
    name: str
    summary: str
    category: str
    star_dimensions: list[str]
    behavioral_hook: str
    quantified: dict
    raw_excerpt: str
    confidence: float
    user_confirmed: bool
    has_temporal_anchor: bool
    has_concrete_action: bool
    has_outcome: bool
    captured_at: datetime
    last_verified_at: Optional[datetime]
    last_used_at: Optional[datetime]
    use_count: int
    is_archived: bool
    source_session_id: Optional[int]


class IndexResponse(BaseModel):
    user_key: str
    total: int
    pending_confirm_count: int
    items: list[ExperienceIndexItem]


class ExperienceListResponse(BaseModel):
    total: int
    items: list[ExperienceDetail]


class EditExperienceIn(BaseModel):
    summary: Optional[str] = Field(default=None, max_length=120)
    behavioral_hook: Optional[str] = Field(default=None, max_length=2000)
    star_dimensions: Optional[list[str]] = None
    quantified: Optional[dict] = None


# ---------- helpers ----------------------------------------------------------


def _require_authenticated_user_key(x_resume_user_key: str) -> str:
    """Reject reserved keys (demo/guest/empty). Real users only."""
    key = (x_resume_user_key or '').strip()
    if not key or key in _RESERVED_USER_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='AUTH_REQUIRED',
        )
    return key


def _load_owned_experience(db: Session, exp_id: int, user_key: str) -> StudentExperience:
    row = db.query(StudentExperience).filter(StudentExperience.id == exp_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail='NOT_FOUND')
    if str(getattr(row, 'user_key', '') or '') != user_key:
        # Forbidden rather than 404 to make the boundary explicit; the id
        # itself is not secret.
        raise HTTPException(status_code=403, detail='FORBIDDEN')
    return row


def _to_index_item(row: StudentExperience) -> ExperienceIndexItem:
    captured = row.captured_at or datetime.utcnow()
    age = max(0, (datetime.utcnow() - captured).days)
    try:
        dims = json.loads(row.star_dimensions_json or '[]')
        if not isinstance(dims, list):
            dims = []
    except (TypeError, ValueError):
        dims = []
    return ExperienceIndexItem(
        id=int(row.id),
        summary=row.summary or '',
        category=row.category or 'experience',
        star_dimensions=dims,
        confidence=float(row.confidence or 0.0),
        user_confirmed=bool(row.user_confirmed),
        captured_at=captured,
        age_days=age,
    )


def _to_detail(row: StudentExperience) -> ExperienceDetail:
    try:
        dims = json.loads(row.star_dimensions_json or '[]')
        if not isinstance(dims, list):
            dims = []
    except (TypeError, ValueError):
        dims = []
    try:
        quantified = json.loads(row.quantified_json or '{}')
        if not isinstance(quantified, dict):
            quantified = {}
    except (TypeError, ValueError):
        quantified = {}
    return ExperienceDetail(
        id=int(row.id),
        name=row.name or '',
        summary=row.summary or '',
        category=row.category or 'experience',
        star_dimensions=dims,
        behavioral_hook=row.behavioral_hook or '',
        quantified=quantified,
        raw_excerpt=row.raw_excerpt or '',
        confidence=float(row.confidence or 0.0),
        user_confirmed=bool(row.user_confirmed),
        has_temporal_anchor=bool(row.has_temporal_anchor),
        has_concrete_action=bool(row.has_concrete_action),
        has_outcome=bool(row.has_outcome),
        captured_at=row.captured_at or datetime.utcnow(),
        last_verified_at=row.last_verified_at,
        last_used_at=row.last_used_at,
        use_count=int(row.use_count or 0),
        is_archived=bool(row.is_archived),
        source_session_id=row.source_session_id,
    )


# ---------- endpoints --------------------------------------------------------


@router.get('/index', response_model=IndexResponse)
def get_index(
    x_resume_user_key: str = Header(default=''),
    include_archived: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """Always-on summary index — meant to be injected as a system-prompt block
    on every chat/interview turn. One row per experience, just the summary."""
    user_key = _require_authenticated_user_key(x_resume_user_key)
    q = db.query(StudentExperience).filter(StudentExperience.user_key == user_key)
    if not include_archived:
        q = q.filter(StudentExperience.is_archived.is_(False))
    rows = q.order_by(StudentExperience.captured_at.desc()).all()
    pending = sum(1 for r in rows if not bool(r.user_confirmed))
    return IndexResponse(
        user_key=user_key,
        total=len(rows),
        pending_confirm_count=pending,
        items=[_to_index_item(r) for r in rows],
    )


@router.get('/experiences', response_model=ExperienceListResponse)
def list_experiences(
    x_resume_user_key: str = Header(default=''),
    category: Optional[str] = Query(default=None),
    dimension: Optional[str] = Query(default=None),
    confirmed_only: bool = Query(default=False),
    include_archived: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Detail retrieval — used by panel + (future) interview runtime."""
    user_key = _require_authenticated_user_key(x_resume_user_key)
    q = db.query(StudentExperience).filter(StudentExperience.user_key == user_key)
    if category:
        q = q.filter(StudentExperience.category == category)
    if confirmed_only:
        q = q.filter(StudentExperience.user_confirmed.is_(True))
    if not include_archived:
        q = q.filter(StudentExperience.is_archived.is_(False))
    rows = q.order_by(StudentExperience.captured_at.desc()).limit(limit * 4).all()

    if dimension:
        # SQLite JSON-array contains needs Python-side filter (no JSON1 dep).
        filtered: list[StudentExperience] = []
        for r in rows:
            try:
                dims = json.loads(r.star_dimensions_json or '[]')
            except (TypeError, ValueError):
                dims = []
            if isinstance(dims, list) and dimension in dims:
                filtered.append(r)
        rows = filtered[:limit]
    else:
        rows = rows[:limit]

    return ExperienceListResponse(
        total=len(rows),
        items=[_to_detail(r) for r in rows],
    )


@router.post('/experiences/{exp_id}/confirm', response_model=ExperienceDetail)
def confirm_experience(
    exp_id: int,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    user_key = _require_authenticated_user_key(x_resume_user_key)
    row = _load_owned_experience(db, exp_id, user_key)
    row.user_confirmed = True
    row.last_verified_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _to_detail(row)


@router.patch('/experiences/{exp_id}', response_model=ExperienceDetail)
def edit_experience(
    exp_id: int,
    payload: EditExperienceIn,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    """User-edit. raw_excerpt is deliberately immutable — it's the audit anchor."""
    user_key = _require_authenticated_user_key(x_resume_user_key)
    row = _load_owned_experience(db, exp_id, user_key)

    if payload.summary is not None:
        row.summary = payload.summary.strip()[:120]
        # NOTE: we deliberately do NOT recompute summary_hash here. The dedup
        # key is set at insertion time and the user editing summary should not
        # silently merge their row with another one. If they want to dedupe,
        # they should archive the dupe explicitly.
    if payload.behavioral_hook is not None:
        row.behavioral_hook = payload.behavioral_hook.strip()[:2000]
    if payload.star_dimensions is not None:
        # If user is editing, they've reviewed it — accept as authoritative.
        row.star_dimensions_json = json.dumps(payload.star_dimensions, ensure_ascii=False)
    if payload.quantified is not None:
        row.quantified_json = json.dumps(payload.quantified, ensure_ascii=False)

    row.user_confirmed = True
    row.last_verified_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _to_detail(row)


@router.post('/experiences/{exp_id}/archive', response_model=ExperienceDetail)
def archive_experience(
    exp_id: int,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    """Soft-delete: hide from index + interview retrieval, preserve audit trail.
    User can un-archive later with PATCH if needed."""
    user_key = _require_authenticated_user_key(x_resume_user_key)
    row = _load_owned_experience(db, exp_id, user_key)
    row.is_archived = True
    db.commit()
    db.refresh(row)
    return _to_detail(row)


@router.delete('/experiences/{exp_id}', status_code=204)
def delete_experience(
    exp_id: int,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    user_key = _require_authenticated_user_key(x_resume_user_key)
    row = _load_owned_experience(db, exp_id, user_key)
    db.delete(row)
    db.commit()
    return None
