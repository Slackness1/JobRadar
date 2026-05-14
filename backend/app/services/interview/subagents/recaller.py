"""ExperienceRecaller — fetches relevant STAR-tagged experiences from
account_memory for use as private hints in the main interview prompt.

This subagent has **no LLM call in v1** (per design Q2). It's a pure SQL +
Python scorer over the account_memory experience rows. Future PRs may flip
``INTERVIEW_SUBAGENT_RECALLER_USE_LLM`` to add an LLM rerank pass — that
hook is left as an unused config flag for now.

Selection algorithm (see design §4.1):

1. Fetch all non-archived, non-superseded experience rows for ``user_key``
2. Filter by ``star_dimensions`` overlap with ``current_topic_dimensions``
3. Drop rows whose ``raw_excerpt`` already appears in ``transcript_so_far``
   (the student already told this story this session — surfacing again
   would feel like the AI doesn't remember the conversation)
4. Score: ``confidence × recency_decay × use_count_boost``
5. Truncate to ``max_results``

Failure modes are surfaced via ``no_match_reason`` rather than as exceptions
or empty success — the orchestrator branches on it to decide whether to
inject hints or fall through to plain interview behavior.
"""
from __future__ import annotations

import asyncio
import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import AccountMemory
from app.services.interview.subagents.base import Subagent


# Mirror the reserved-key set from the dispatcher — must stay in sync.
# Demo/guest sessions share user_keys across real users, so recall would
# leak experiences.
_RESERVED_USER_KEYS = frozenset({"__demo__", "__guest__", ""})


# Recency decay tunable: τ in `exp(-age / τ)`. 90 days means a 90-day-old
# experience is worth ~37% of a brand-new one. Captured in days, not
# seconds, so DB-level datetime resolution is sufficient.
_RECENCY_TAU_DAYS = 90.0


@dataclass
class RecallerInput:
    """Required parameters for one Recaller invocation.

    ``db`` is passed in by the orchestrator — recaller doesn't open its own
    SessionLocal (avoids long-lived session leakage). The session must
    remain valid for the duration of ``invoke``.
    """

    db: Session
    user_key: str
    target_job: str = ""
    current_topic_dimensions: list[str] = field(default_factory=list)
    transcript_so_far: list[dict] = field(default_factory=list)
    max_results: int = 3


class ExperienceRecaller(Subagent[RecallerInput, dict]):
    subagent_type = "experience_recaller"
    timeout_seconds = 5  # SQL + Python only — should be sub-second normally

    async def _run(self, payload: RecallerInput) -> dict:
        # Pure SQL/Python work — offload to thread pool so the orchestrator's
        # event loop can interleave with other subagents.
        return await asyncio.to_thread(self._recall_sync, payload)

    def _recall_sync(self, payload: RecallerInput) -> dict:
        # ── 1. user_key gate ─────────────────────────────────────────────────
        key = (payload.user_key or "").strip()
        if not key or key in _RESERVED_USER_KEYS:
            return _empty_summary(kb_size=0, reason="unauthorized_or_demo")

        # ── 2. fetch all eligible rows ───────────────────────────────────────
        rows: list[AccountMemory] = (
            payload.db.query(AccountMemory)
            .filter(
                AccountMemory.user_key == key,
                AccountMemory.category == "experience",
                AccountMemory.is_archived.is_(False),
                AccountMemory.superseded_by_id.is_(None),
            )
            .all()
        )
        kb_size = len(rows)
        if not rows:
            return _empty_summary(kb_size=0, reason="kb_empty")

        # ── 3. dimension filter ──────────────────────────────────────────────
        topic_dims = {d for d in (payload.current_topic_dimensions or []) if d}
        candidates: list[tuple[AccountMemory, dict, set[str]]] = []
        for row in rows:
            payload_obj = _safe_load_payload(row.payload_json)
            row_dims = {
                d for d in (payload_obj.get("star_dimensions") or []) if d
            }
            if topic_dims and not (row_dims & topic_dims):
                continue
            candidates.append((row, payload_obj, row_dims))

        if not candidates:
            return _empty_summary(kb_size=kb_size, reason="no_dimension_match")

        # ── 4. transcript dedup ──────────────────────────────────────────────
        transcript_text = _flatten_transcript(payload.transcript_so_far)
        filtered = [
            (row, payload_obj, row_dims)
            for row, payload_obj, row_dims in candidates
            if not _already_in_transcript(row, transcript_text)
        ]
        if not filtered:
            return _empty_summary(kb_size=kb_size, reason="all_used")

        # ── 5. score + sort ──────────────────────────────────────────────────
        now = datetime.utcnow()
        scored: list[tuple[float, AccountMemory, dict, set[str]]] = []
        for row, payload_obj, row_dims in filtered:
            score = _score_row(row, now)
            scored.append((score, row, payload_obj, row_dims))
        scored.sort(key=lambda t: t[0], reverse=True)
        top = scored[: max(1, payload.max_results)]

        # ── 6. shape output ──────────────────────────────────────────────────
        experiences = [
            _shape_experience(row, payload_obj, row_dims, now)
            for _score, row, payload_obj, row_dims in top
        ]
        return {
            "experiences": experiences,
            "kb_size": kb_size,
            "no_match_reason": None,
        }


# ─── helpers ─────────────────────────────────────────────────────────────────


def _empty_summary(*, kb_size: int, reason: str) -> dict:
    return {
        "experiences": [],
        "kb_size": kb_size,
        "no_match_reason": reason,
    }


def _safe_load_payload(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        out = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return out if isinstance(out, dict) else {}


def _flatten_transcript(messages: list[dict]) -> str:
    """Join transcript message contents for substring containment check."""
    parts: list[str] = []
    for m in messages or []:
        content = m.get("content") if isinstance(m, dict) else None
        if content:
            parts.append(str(content))
    return " ".join(parts)


def _already_in_transcript(row: AccountMemory, transcript: str) -> bool:
    """True if this experience's raw_excerpt is contained in transcript so
    far — student already volunteered the story, don't re-surface."""
    raw = (row.raw_excerpt or "").strip()
    if not raw or not transcript:
        return False
    # Use raw_excerpt as the substring probe — it's the verbatim quote and
    # therefore the most reliable signal that the same anecdote is being
    # discussed.
    return raw in transcript


def _score_row(row: AccountMemory, now: datetime) -> float:
    """Recency-decayed confidence × unused-bonus.

    - confidence    : in [0,1], LLM self-rated when row was extracted
    - recency_decay : exp(-age/τ) — τ=90 days
    - use_count_boost: 1.5 if never surfaced before, 1.0 if used
    """
    captured = row.captured_at or now
    age_days = max(0, (now - captured).days)
    recency = math.exp(-age_days / _RECENCY_TAU_DAYS)
    use_boost = 1.5 if (int(row.use_count or 0) == 0) else 1.0
    conf = float(row.confidence or 0.0)
    return conf * recency * use_boost


def _shape_experience(
    row: AccountMemory,
    payload_obj: dict,
    row_dims: set[str],
    now: datetime,
) -> dict:
    captured = row.captured_at or now
    age_days = max(0, (now - captured).days)
    raw = row.raw_excerpt or ""
    return {
        "id": int(row.id),
        "summary": row.summary or "",
        "behavioral_hook": str(payload_obj.get("behavioral_hook") or ""),
        "dimensions": sorted(row_dims),
        "age_days": age_days,
        "confidence": float(row.confidence or 0.0),
        "raw_excerpt_snippet": raw[:200],
    }


__all__ = ["ExperienceRecaller", "RecallerInput"]
