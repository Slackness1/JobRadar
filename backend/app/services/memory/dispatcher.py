"""Single write entry point for ``account_memory``.

All writes to the unified memory table MUST go through ``write_memory`` (or
``supersede_memory`` / ``archive_memory``) — no caller should ``db.add(...)``
an ``AccountMemory`` row directly. This is the chokepoint that:

1. Enforces ``UNIFIED_MEMORY_ENABLED`` feature flag
2. Blocks demo / guest / empty user_keys at the door
3. Validates payload against category-specific pydantic schema
4. Computes stable ``summary_hash`` for dedup
5. Returns ``(action, row)`` so callers can react to insert vs refresh vs blocked
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.config import UNIFIED_MEMORY_ENABLED
from app.models import AccountMemory
from app.services.memory.schemas import validate_payload


logger = logging.getLogger(__name__)


# Reserved user_keys that must NEVER produce account-memory rows. Demo &
# guest sessions are multi-tenant under one key — writing memory there would
# leak across users.
_RESERVED_USER_KEYS = frozenset({"__demo__", "__guest__", ""})


WriteAction = Literal["inserted", "refreshed", "blocked", "validation_error"]


@dataclass
class WriteOutcome:
    """Result of a single ``write_memory`` call.

    ``action`` reports what happened. On non-success paths ``row`` is None and
    ``reason`` explains why. Callers should NOT raise on ``blocked`` —
    blocking is expected (demo/guest/flag-off).
    """

    action: WriteAction
    row: Optional[AccountMemory] = None
    reason: str = ""


def _normalize_for_hash(text: str) -> str:
    """Collapse whitespace + lowercase. Same rule used across writers so
    parallel modules produce identical hashes for "same fact, different
    phrasing"."""
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def compute_summary_hash(user_key: str, category: str, summary: str) -> str:
    """Stable per-(user, category, summary) dedup hash.

    Including ``category`` means the same summary text under different
    categories doesn't collide (rare but possible — e.g., "Python" as both
    skill_claim and identity_fact would be different rows).
    """
    payload = f"{user_key}::{category}::{_normalize_for_hash(summary)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _is_blocked_user_key(user_key: str) -> tuple[bool, str]:
    key = (user_key or "").strip()
    if not key:
        return True, "reserved_user_key:<empty>"
    if key in _RESERVED_USER_KEYS:
        return True, f"reserved_user_key:{key}"
    return False, ""


def write_memory(
    db: Session,
    *,
    user_key: str,
    category: str,
    summary: str,
    payload: dict | BaseModel,
    source_module: str,
    source_session_id: Optional[int] = None,
    source_message_id: Optional[int] = None,
    raw_excerpt: str = "",
    confidence: float = 1.0,
    auto_confirm_threshold: float = 0.85,
    commit: bool = True,
    linked_field_paths: list[str] | None = None,
    linked_track: str = '',
    linked_job_id: str = '',
) -> WriteOutcome:
    """Insert-or-refresh a single account_memory row. Dedup keyed on
    (user_key, category, normalized summary).

    Parameters
    ----------
    db
        Active SQLAlchemy session. Caller owns transactional scope; we commit
        only when ``commit=True``.
    user_key
        Account identity. Reserved keys (demo/guest/empty) yield ``blocked``.
    category
        One of the keys in ``CATEGORY_TO_SCHEMA``. Unknown category yields
        ``validation_error``.
    summary
        Short index-side string. Becomes the always-on context summary, so
        keep it ≤80 chars where practical.
    payload
        Either a dict (will be validated) or an already-constructed pydantic
        model of the matching schema class.
    source_module
        Module that produced this row. Used for audit + replay.
    confidence
        LLM-rated 0-1 confidence. ``confidence >= auto_confirm_threshold``
        sets ``user_confirmed=True`` automatically.

    Returns
    -------
    WriteOutcome
        ``action`` ∈ {inserted, refreshed, blocked, validation_error}.
        On non-success paths, ``row`` is ``None`` and ``reason`` is set.
    """
    # ── 1. flag gate ─────────────────────────────────────────────────────────
    if not UNIFIED_MEMORY_ENABLED:
        return WriteOutcome(action="blocked", reason="flag_off")

    # ── 2. user_key gate ────────────────────────────────────────────────────
    blocked, reason = _is_blocked_user_key(user_key)
    if blocked:
        return WriteOutcome(action="blocked", reason=reason)

    # ── 3. payload validation (raises ValueError on unknown category) ──────
    try:
        validated = validate_payload(category, payload)
    except (ValueError, ValidationError) as exc:
        logger.warning("memory dispatcher: payload validation failed: %s", exc)
        return WriteOutcome(action="validation_error", reason=str(exc)[:300])

    # ── 4. summary normalization + hash ─────────────────────────────────────
    cleaned_summary = (summary or "").strip()
    if not cleaned_summary:
        return WriteOutcome(action="validation_error", reason="empty_summary")
    if len(cleaned_summary) > 200:
        cleaned_summary = cleaned_summary[:200]

    digest = compute_summary_hash(user_key, category, cleaned_summary)

    # ── 5. dedup check ──────────────────────────────────────────────────────
    existing = (
        db.query(AccountMemory)
        .filter(
            AccountMemory.user_key == user_key,
            AccountMemory.summary_hash == digest,
        )
        .first()
    )
    if existing is not None:
        # User archived this earlier — respect their decision; don't re-surface
        # by silently un-archiving. Caller can call un_archive explicitly.
        if not bool(getattr(existing, "is_archived", False)):
            existing.last_verified_at = datetime.utcnow()
            if commit:
                db.commit()
        return WriteOutcome(action="refreshed", row=existing)

    # ── 6. insert ───────────────────────────────────────────────────────────
    auto_confirm = bool(confidence >= auto_confirm_threshold)
    # `linked_field_paths` lets Plan 1 resync logic later find this row when
    # the matching bullet text is edited. Caller (chat/plan extractor) passes
    # paths like ["internships.0.bullets.2"]; empty/None → general memory.
    safe_paths = [str(p) for p in (linked_field_paths or []) if p]
    row = AccountMemory(
        user_key=user_key,
        category=category,
        summary=cleaned_summary,
        payload_json=validated.model_dump_json(),
        summary_hash=digest,
        source_module=source_module,
        source_session_id=source_session_id,
        source_message_id=source_message_id,
        raw_excerpt=(raw_excerpt or "")[:2000],
        confidence=float(confidence),
        user_confirmed=auto_confirm,
        captured_at=datetime.utcnow(),
        last_verified_at=datetime.utcnow(),
        linked_field_paths=json.dumps(safe_paths),
        linked_track=str(linked_track or '').strip(),
        linked_job_id=str(linked_job_id or '').strip(),
    )
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    else:
        db.flush()
    return WriteOutcome(action="inserted", row=row)


def supersede_memory(
    db: Session,
    *,
    old_id: int,
    new_outcome: WriteOutcome,
    commit: bool = True,
) -> bool:
    """Link ``old_id`` row as superseded by the row in ``new_outcome``.

    Used for preference/identity_fact evolution — user changes mind, new row
    replaces old. The old row stays for audit; read paths default-filter
    ``WHERE superseded_by_id IS NULL`` to skip it.

    Returns True if the link was created, False if either side is missing.
    """
    if new_outcome.action != "inserted" or new_outcome.row is None:
        # Nothing to supersede TO (refreshed/blocked/error paths).
        return False
    old_row = db.query(AccountMemory).filter(AccountMemory.id == old_id).first()
    if old_row is None:
        return False
    if int(getattr(old_row, "id", 0)) == int(new_outcome.row.id):
        # No-op: cannot supersede self.
        return False
    old_row.superseded_by_id = new_outcome.row.id
    if commit:
        db.commit()
    return True


def archive_memory(
    db: Session,
    *,
    memory_id: int,
    user_key: str,
    commit: bool = True,
) -> bool:
    """Soft-delete: hide from read paths but preserve audit. The user_key arg
    is mandatory and checked — defense against id-guessing across users."""
    row = db.query(AccountMemory).filter(AccountMemory.id == memory_id).first()
    if row is None:
        return False
    if str(getattr(row, "user_key", "")) != user_key:
        return False
    row.is_archived = True
    if commit:
        db.commit()
    return True


__all__ = [
    "WriteAction",
    "WriteOutcome",
    "write_memory",
    "supersede_memory",
    "archive_memory",
    "compute_summary_hash",
]
