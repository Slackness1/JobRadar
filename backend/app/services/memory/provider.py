"""StudentMemoryProvider — surfaces account_memory rows as private hint blocks.

Read path for the unified-memory store. Pulls a small budget of the most
useful facts (least recently used + highest confidence) for the active
user_key and formats them as a system-prompt block.

Categories surfaced (per design doc):
    experience      — STAR-tagged anecdotes (also used by ExperienceRecaller
                      inside the interview orchestrator; safe to surface here
                      too — Recaller dedups internally on raw_excerpt)
    skill_claim     — "I know X" facts the student has confirmed
    preference      — track / city / company preferences
    identity_fact   — degree, school, graduation year
    goal            — target job direction
    evidence        — Plan-Mode evidence rows (when promoted from plan_json)

Reserved user_keys (__demo__ / __guest__ / "") are skipped to avoid
cross-user leakage in shared sessions.
"""
from __future__ import annotations

import json
import logging

from app.models import AccountMemory
from app.services.llm_context.base import (
    PURPOSE_CHAT,
    PURPOSE_INTERVIEW_QUESTION,
    PURPOSE_INTERVIEW_SCORE,
    ContextRequest,
)

logger = logging.getLogger(__name__)


_RESERVED_USER_KEYS = frozenset({"__demo__", "__guest__", ""})

# Categories we surface — mirrors RecallerInput defaults plus identity/preference
# rows that are useful in CHAT but not picked up by ExperienceRecaller.
_SURFACED_CATEGORIES = (
    "experience",
    "skill_claim",
    "preference",
    "identity_fact",
    "goal",
    "evidence",
)

_DEFAULT_LIMIT = 5


class StudentMemoryProvider:
    name = "student_memory"

    def applies_to(self, req: ContextRequest) -> bool:
        if req.purpose not in (PURPOSE_CHAT, PURPOSE_INTERVIEW_QUESTION, PURPOSE_INTERVIEW_SCORE):
            return False
        key = (req.user_key or "").strip()
        if not key or key in _RESERVED_USER_KEYS:
            return False
        return True

    def fetch(self, req: ContextRequest) -> str:
        key = (req.user_key or "").strip()
        rows = (
            req.db.query(AccountMemory)
            .filter(
                AccountMemory.user_key == key,
                AccountMemory.category.in_(_SURFACED_CATEGORIES),
                AccountMemory.is_archived.is_(False),
                AccountMemory.superseded_by_id.is_(None),
            )
            # Least-used first so we rotate through the KB instead of always
            # surfacing the same top items.
            .order_by(AccountMemory.use_count.asc().nullsfirst(),
                      AccountMemory.confidence.desc().nullslast())
            .limit(_DEFAULT_LIMIT)
            .all()
        )
        if not rows:
            return ""

        # Group by category for readability in the prompt.
        by_cat: dict[str, list[AccountMemory]] = {}
        for r in rows:
            by_cat.setdefault(r.category or "misc", []).append(r)

        lines: list[str] = ["[student_memory · 用户私密档案 — 仅供你判断匹配度，不要原文复述]"]
        for cat, items in by_cat.items():
            lines.append(f"\n  · {cat}:")
            for r in items:
                summary = (r.summary or "").strip()
                if not summary:
                    # Fall back to short payload preview.
                    payload = _safe_load_payload(r.payload_json)
                    summary = str(payload.get("behavioral_hook") or payload.get("rule") or "").strip()[:140]
                if summary:
                    lines.append(f"    - {summary}")
        return "\n".join(lines)


def _safe_load_payload(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        out = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return out if isinstance(out, dict) else {}


__all__ = ["StudentMemoryProvider"]
