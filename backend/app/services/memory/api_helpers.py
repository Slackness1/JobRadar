"""HTTP-facing helpers for ``account_memory``.

Phase 0 (P0-2 of main-workspace-redesign-2026-05-20). Exposes:

- ``serialize_entry``           — AccountMemory row → JSON-safe dict
- ``list_entries_by_category``  — fetch all non-archived rows for a user_key,
  grouped by the 8 canonical categories
- ``MEMORY_CATEGORIES``         — canonical category order for the API

The router calls these directly; service-layer business logic (dedup, payload
validation, etc.) still lives in ``dispatcher.py`` and ``schemas.py``.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.models import AccountMemory


logger = logging.getLogger(__name__)


# Canonical category ordering — the 8 categories from
# docs/unified-memory-and-plan-mode-2026-05-13.md, listed in the order the UI
# prefers (experience first per A-5 "经历主、其他次").
MEMORY_CATEGORIES: tuple[str, ...] = (
    "experience",
    "skill_claim",
    "preference",
    "identity_fact",
    "evidence",
    "goal",
    "commitment",
    "weakness_signal",
)


def _to_iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def serialize_entry(row: AccountMemory) -> dict[str, Any]:
    """Stable JSON shape for one row. Payload is parsed from JSON text into
    a dict (or empty dict on parse failure)."""
    try:
        payload = json.loads(str(row.payload_json or "{}"))
    except (json.JSONDecodeError, TypeError):
        payload = {}
    return {
        "id": int(row.id),
        "category": str(row.category or ""),
        "summary": str(row.summary or ""),
        "payload": payload,
        "confidence": float(row.confidence or 0.0),
        "user_confirmed": bool(row.user_confirmed),
        "use_count": int(row.use_count or 0),
        "is_archived": bool(row.is_archived),
        "superseded_by_id": (
            int(row.superseded_by_id) if row.superseded_by_id is not None else None
        ),
        "source_module": str(row.source_module or ""),
        "source_session_id": (
            int(row.source_session_id) if row.source_session_id is not None else None
        ),
        "raw_excerpt": str(row.raw_excerpt or ""),
        "captured_at": _to_iso(row.captured_at),
        "last_verified_at": _to_iso(row.last_verified_at),
        "last_used_at": _to_iso(row.last_used_at),
    }


def list_entries_by_category(
    db: Session,
    *,
    user_key: str,
    include_archived: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    """Return a dict keyed on the 8 canonical categories, each value a list
    of serialized entries (most recently captured first).

    Reserved user_keys (``__demo__`` / ``__guest__`` / empty) always yield
    empty buckets — they are multi-tenant and writing to them would leak
    across users (see dispatcher.py for the matching write-side guard).
    """
    out: dict[str, list[dict[str, Any]]] = {cat: [] for cat in MEMORY_CATEGORIES}
    key = (user_key or "").strip()
    if not key or key in {"__demo__", "__guest__"}:
        return out

    query = db.query(AccountMemory).filter(AccountMemory.user_key == key)
    if not include_archived:
        query = query.filter(
            (AccountMemory.is_archived.is_(False)) | (AccountMemory.is_archived.is_(None))
        )
    rows: Iterable[AccountMemory] = query.order_by(
        AccountMemory.captured_at.desc().nulls_last()
        if hasattr(AccountMemory.captured_at.desc(), "nulls_last")
        else AccountMemory.captured_at.desc()
    ).all()

    for row in rows:
        cat = str(row.category or "")
        if cat not in out:
            # Unknown category — surface it under a synthetic bucket so the
            # row isn't silently dropped; the API consumer can flag it.
            out.setdefault(cat, []).append(serialize_entry(row))
            continue
        out[cat].append(serialize_entry(row))

    return out


__all__ = [
    "MEMORY_CATEGORIES",
    "serialize_entry",
    "list_entries_by_category",
]
