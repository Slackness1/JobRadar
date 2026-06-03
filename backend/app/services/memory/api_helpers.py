"""HTTP-facing helpers for ``account_memory``.

Phase 0 (P0-2 of main-workspace-redesign-2026-05-20). Exposes:

- ``serialize_entry``           — AccountMemory row → JSON-safe dict
- ``list_entries_by_category``  — fetch all non-archived rows for a user_key,
  grouped by the 8 canonical categories
- ``MEMORY_CATEGORIES``         — canonical category order for the API
- ``relevant_memory_for_bullet`` — Phase 1 (BE-2): fuzzy-match memory rows
  against a resume bullet to feed the thesis-aware rewrite prompt

The router calls these directly; service-layer business logic (dedup, payload
validation, etc.) still lives in ``dispatcher.py`` and ``schemas.py``.
"""
from __future__ import annotations

import json
import logging
import re
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
    # linked_field_paths — JSON list[str] of resume bullet paths this row was
    # extracted from. Used by Plan 1 (Resume-edit ↔ memory sync) so the UI
    # can route "🔄 needs_resync" entries back to plan-mode for that bullet.
    try:
        linked_paths = json.loads(str(getattr(row, 'linked_field_paths', '[]') or '[]'))
        if not isinstance(linked_paths, list):
            linked_paths = []
    except (json.JSONDecodeError, TypeError):
        linked_paths = []
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
        "linked_field_paths": [str(p) for p in linked_paths],
        "needs_resync": bool(getattr(row, 'needs_resync', False)),
        "linked_track": str(getattr(row, 'linked_track', '') or ''),
        "linked_job_id": str(getattr(row, 'linked_job_id', '') or ''),
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


# ─── BE-2: fuzzy memory retrieval for rewrite thesis ──────────────────────────
#
# When generating a "v2 thesis-aware" rewrite for a specific resume bullet, the
# rewriter needs to inject relevant ``experience`` + ``skill_claim`` rows from
# ``account_memory`` so the LLM has the student's own non-公共 details (not just
# what's in the bullet itself).
#
# The match is intentionally simple — character-level n-gram overlap on the
# Chinese summary text. We avoid embeddings / heavyweight NLP here because:
#   (a) summaries are short (≤200 chars) so token-set overlap is good enough
#   (b) latency budget is tight (rewrite path runs in front of the user)
#   (c) recall > precision: a noisy match is fine — the LLM filters by reading
#       the bullet + memory rows together in-context.
#
# Categories surfaced: ``experience`` + ``skill_claim`` are the strong rows
# (concrete project / role detail used to ground rewrites). ``preference`` is
# pulled in as a SOFT boost (Fix #2, 2026-05-20) — preferences don't supply
# detail but they signal target-track alignment (e.g. "想做 buy-side 消费"
# helps a v2 rewrite emphasise consumer-research angle).

_RELEVANT_CATEGORIES_FOR_BULLET: tuple[str, ...] = (
    "experience",
    "skill_claim",
)
_BOOST_CATEGORIES_FOR_BULLET: tuple[str, ...] = (
    "preference",
)
_BOOST_MAX = 2  # at most 2 preference rows appended (most-used first)

_CJK_OR_WORD_RE = re.compile(r"[一-鿿]|[A-Za-z0-9]+")


def _tokenize_for_match(text: str) -> set[str]:
    """Token set for character-level overlap scoring.

    Each CJK char counts as one token (Chinese is mostly one-char-one-morpheme
    for this domain); ASCII runs are folded to a single lowercase token so
    "Python"/"python" match. Returns lowercase set.
    """
    if not text:
        return set()
    tokens = set()
    for m in _CJK_OR_WORD_RE.finditer(text):
        t = m.group(0)
        if t.isascii():
            t = t.lower()
            if len(t) <= 1:
                continue
        tokens.add(t)
    return tokens


def _overlap_score(a_tokens: set[str], b_tokens: set[str]) -> float:
    """Jaccard-like overlap normalized by the shorter set so a long memory
    summary doesn't get penalised against a short bullet."""
    if not a_tokens or not b_tokens:
        return 0.0
    inter = a_tokens & b_tokens
    denom = min(len(a_tokens), len(b_tokens))
    return len(inter) / denom if denom else 0.0


def relevant_memory_for_bullet(
    db: Session,
    *,
    user_key: str,
    bullet_text: str,
    k: int = 3,
    min_score: float = 0.10,
    active_job_id: str = '',
    target_track: str = '',
) -> list[dict[str, Any]]:
    """Top-k ``experience`` / ``skill_claim`` rows matching the bullet.

    Returned dicts use the same shape as ``serialize_entry`` plus a synthetic
    ``match_score`` field so callers (and tests) can inspect why a row was
    picked. Sorted by ``match_score`` descending.

    Reserved user_keys return ``[]`` (same multi-tenant guard as
    ``list_entries_by_category``).
    """
    key = (user_key or "").strip()
    if not key or key in {"__demo__", "__guest__"}:
        return []
    if not (bullet_text or "").strip():
        return []
    if k <= 0:
        return []

    bullet_tokens = _tokenize_for_match(bullet_text)
    if not bullet_tokens:
        return []

    rows = (
        db.query(AccountMemory)
        .filter(
            AccountMemory.user_key == key,
            AccountMemory.category.in_(_RELEVANT_CATEGORIES_FOR_BULLET),
            (AccountMemory.is_archived.is_(False)) | (AccountMemory.is_archived.is_(None)),
            AccountMemory.superseded_by_id.is_(None),
        )
        .all()
    )

    active_job_id_clean = (active_job_id or "").strip()
    target_track_clean = (target_track or "").strip()
    scored: list[tuple[float, AccountMemory]] = []
    for row in rows:
        # Use summary + raw_excerpt + payload behavioral_hook for token pool
        # — summary alone is too short for stable overlap.
        text_pool = [str(row.summary or ""), str(row.raw_excerpt or "")]
        try:
            payload = json.loads(str(row.payload_json or "{}"))
            if isinstance(payload, dict):
                hook = payload.get("behavioral_hook")
                if isinstance(hook, str):
                    text_pool.append(hook)
                skill = payload.get("skill_name")
                if isinstance(skill, str):
                    text_pool.append(skill)
        except (json.JSONDecodeError, TypeError):
            pass

        candidate_tokens = _tokenize_for_match(" ".join(text_pool))
        score = _overlap_score(bullet_tokens, candidate_tokens)
        # Plan ② Job plan-mode (2026-05-21): if rewriting in the context of a
        # specific job, boost memory rows captured while customising for that
        # same job by +0.5 — pushes per-job customisation evidence to the top.
        if active_job_id_clean and str(getattr(row, 'linked_job_id', '') or '') == active_job_id_clean:
            score += 0.5
        # 赛道上下文 boost:记忆是账号级跨简历共享的,但召回时按当前简历目标
        # 赛道排序 —— linked_track 命中目标赛道 +0.4,让对口经历浮上来。
        if target_track_clean and str(getattr(row, 'linked_track', '') or '') == target_track_clean:
            score += 0.4
        if score >= min_score:
            scored.append((score, row))

    scored.sort(key=lambda x: x[0], reverse=True)
    out: list[dict[str, Any]] = []
    for score, row in scored[:k]:
        entry = serialize_entry(row)
        entry["match_score"] = round(float(score), 4)
        out.append(entry)

    # Append up to _BOOST_MAX preference rows as a target-track signal (Fix #2,
    # 2026-05-20). These are NOT re-ranked against bullet_tokens — they're
    # global alignment hints, ordered by use_count desc then created_at desc.
    boost_rows = (
        db.query(AccountMemory)
        .filter(
            AccountMemory.user_key == key,
            AccountMemory.category.in_(_BOOST_CATEGORIES_FOR_BULLET),
            (AccountMemory.is_archived.is_(False)) | (AccountMemory.is_archived.is_(None)),
            AccountMemory.superseded_by_id.is_(None),
        )
        .order_by(AccountMemory.use_count.desc(), AccountMemory.captured_at.desc())
        .limit(_BOOST_MAX)
        .all()
    )
    for row in boost_rows:
        entry = serialize_entry(row)
        entry["match_score"] = 0.0  # boost rows aren't scored against bullet
        out.append(entry)
    return out


def diff_changed_field_paths(
    old_profile: dict | None,
    new_profile: dict | None,
) -> list[str]:
    """Return field_paths whose bullet text differs between two profile dicts.

    Used by `PUT /confirmed-profile` to detect which resume bullets the
    student edited so the dispatcher can flag corresponding memory rows as
    ``needs_resync=True`` (Plan 1, 2026-05-20).

    Supported paths:
      - ``internships.{i}.bullets.{j}``
      - ``projects.{i}.bullets.{j}``
      - ``education.{i}.highlights.{j}``
      - ``candidate_summary``

    A bullet counts as "changed" if its trimmed text differs (whitespace
    normalised). New / deleted bullets also count — the index changes are
    detected as content diffs at the corresponding position.
    """
    if not isinstance(old_profile, dict) or not isinstance(new_profile, dict):
        return []

    def _trim(s: object) -> str:
        return ' '.join(str(s or '').split())

    changed: list[str] = []

    # candidate_summary (single field)
    if _trim(old_profile.get('candidate_summary')) != _trim(new_profile.get('candidate_summary')):
        changed.append('candidate_summary')

    # iter through list-of-objects-with-bullets sections
    for section, bullet_key in (
        ('internships', 'bullets'),
        ('projects', 'bullets'),
        ('education', 'highlights'),
    ):
        old_items = old_profile.get(section) or []
        new_items = new_profile.get(section) or []
        n = max(len(old_items) if isinstance(old_items, list) else 0,
                len(new_items) if isinstance(new_items, list) else 0)
        for i in range(n):
            old_item = old_items[i] if (isinstance(old_items, list) and i < len(old_items) and isinstance(old_items[i], dict)) else {}
            new_item = new_items[i] if (isinstance(new_items, list) and i < len(new_items) and isinstance(new_items[i], dict)) else {}
            old_bullets = old_item.get(bullet_key) or []
            new_bullets = new_item.get(bullet_key) or []
            m = max(len(old_bullets) if isinstance(old_bullets, list) else 0,
                    len(new_bullets) if isinstance(new_bullets, list) else 0)
            for j in range(m):
                ob = old_bullets[j] if (isinstance(old_bullets, list) and j < len(old_bullets)) else ''
                nb = new_bullets[j] if (isinstance(new_bullets, list) and j < len(new_bullets)) else ''
                if _trim(ob) != _trim(nb):
                    changed.append(f'{section}.{i}.{bullet_key}.{j}')

    return changed


def mark_memory_needs_resync(
    db: Session,
    *,
    user_key: str,
    changed_field_paths: list[str],
) -> int:
    """For each memory row whose ``linked_field_paths`` intersects
    ``changed_field_paths``, set ``needs_resync = True``. Returns the row
    count touched. No-op for reserved user_keys (multi-tenant guard).
    """
    key = (user_key or "").strip()
    if not key or key in {"__demo__", "__guest__"}:
        return 0
    if not changed_field_paths:
        return 0
    changed_set = set(changed_field_paths)

    rows = (
        db.query(AccountMemory)
        .filter(
            AccountMemory.user_key == key,
            (AccountMemory.is_archived.is_(False)) | (AccountMemory.is_archived.is_(None)),
            AccountMemory.superseded_by_id.is_(None),
        )
        .all()
    )
    touched = 0
    for row in rows:
        try:
            linked = json.loads(str(getattr(row, 'linked_field_paths', '[]') or '[]'))
            if not isinstance(linked, list):
                continue
        except (json.JSONDecodeError, TypeError):
            continue
        if any(str(p) in changed_set for p in linked):
            row.needs_resync = True
            touched += 1
    if touched:
        db.commit()
    return touched


__all__ = [
    "MEMORY_CATEGORIES",
    "serialize_entry",
    "list_entries_by_category",
    "relevant_memory_for_bullet",
    "diff_changed_field_paths",
    "mark_memory_needs_resync",
]
