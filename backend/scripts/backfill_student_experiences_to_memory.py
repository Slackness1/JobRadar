"""Phase 0 P0-3 — migrate legacy ``student_experiences`` into ``account_memory``.

Run once per environment (dev DB now; prod DB later via deploy skill). Idempotent
via the existing UniqueConstraint(user_key, summary_hash) — re-runs hit dedup
and only count fresh rows.

Decision context:
    - main-workspace-redesign-2026-05-20 A-9 was砍掉 (no full migration), but
      P0-3 keeps a one-shot backfill so dev DB doesn't accumulate split-brain
      state during the 闭环 build-out (Phase 1+).
    - student_experiences row → account_memory row of the *same category*
      (legacy table already has the discriminator). For category='experience'
      we synthesise a minimal ExperiencePayload from name/behavioral_hook/
      quantified; for the other 3 (skill_claim / preference / identity_fact)
      we build the matching payload from the summary text — best-effort, and
      writer is marked source_module='legacy_backfill' so downstream can spot
      these rows for follow-up curation.

Run:
    cd backend && PYTHONPATH=. .venv/bin/python \\
        scripts/backfill_student_experiences_to_memory.py
"""
from __future__ import annotations

import json
import logging
import sys
from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import AccountMemory, StudentExperience
from app.services.memory.dispatcher import write_memory
from app.services.memory.schemas import ALLOWED_STAR_DIMENSIONS


# Categories that exist in legacy student_experiences. Anything else gets
# skipped + counted (the legacy column never had a CHECK so weird values are
# possible).
_LEGACY_CATEGORIES = {"experience", "skill_claim", "preference", "identity_fact"}

# Stable mapping for the simple cases. For categories where the new payload
# schema requires extra fields not present in the legacy row, we fill best-
# effort defaults; see _build_payload below.
_PREFERENCE_DIMENSIONS = {
    "track", "city", "company_type", "role_family", "remote",
    "comp_band", "industry", "team_size", "english_required",
}


def _safe_json_loads(text: str | None, default: Any) -> Any:
    if not text:
        return default
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


def _experience_payload(row: StudentExperience) -> dict:
    """Build an ExperiencePayload-compatible dict from a legacy experience row."""
    star_dims_raw = _safe_json_loads(row.star_dimensions_json, [])
    star_dims = [
        d for d in (str(x) for x in star_dims_raw)
        if d in ALLOWED_STAR_DIMENSIONS
    ]
    quantified = _safe_json_loads(row.quantified_json, {})
    if not isinstance(quantified, dict):
        quantified = {}
    return {
        "behavioral_hook": (row.behavioral_hook or row.summary or row.name or "")[:1000],
        "star_dimensions": star_dims,
        "quantified": quantified,
        "evidence_ids": [],
    }


def _skill_claim_payload(row: StudentExperience) -> dict:
    """Best-effort SkillClaimPayload — summary text becomes skill_name."""
    skill_name = (row.summary or row.name or "").strip()[:120] or "(unknown)"
    return {
        "skill_name": skill_name,
        "level": None,
        "evidence_ids": [],
    }


def _preference_payload(row: StudentExperience) -> dict:
    """Best-effort PreferencePayload — summary becomes value, default dimension
    'track' (most legacy preference rows were track-style)."""
    value = (row.summary or row.name or "").strip()[:200] or "(unknown)"
    return {
        "dimension": "track",
        "value": value,
        "polarity": "positive",
    }


def _identity_fact_payload(row: StudentExperience) -> dict:
    """Best-effort IdentityFactPayload — default kind 'major' (legacy rows
    were school/major-heavy)."""
    value = (row.summary or row.name or "").strip()[:200] or "(unknown)"
    return {
        "kind": "major",
        "value": value,
    }


def _build_payload(row: StudentExperience) -> dict | None:
    category = str(row.category or "").strip()
    if category == "experience":
        return _experience_payload(row)
    if category == "skill_claim":
        return _skill_claim_payload(row)
    if category == "preference":
        return _preference_payload(row)
    if category == "identity_fact":
        return _identity_fact_payload(row)
    return None


def backfill(db: Session) -> dict[str, int]:
    counters: dict[str, int] = defaultdict(int)
    counters["scanned"] = 0

    rows = db.query(StudentExperience).order_by(StudentExperience.id.asc()).all()
    counters["scanned"] = len(rows)

    for row in rows:
        user_key = str(getattr(row, "user_key", "") or "").strip()
        if not user_key:
            counters["skipped_no_user_key"] += 1
            continue

        category = str(row.category or "").strip()
        if category not in _LEGACY_CATEGORIES:
            counters[f"skipped_unknown_category:{category or '<empty>'}"] += 1
            continue

        payload = _build_payload(row)
        if payload is None:
            counters[f"skipped_payload_build_failed:{category}"] += 1
            continue

        summary = (row.summary or row.name or "").strip()
        if not summary:
            counters["skipped_empty_summary"] += 1
            continue

        outcome = write_memory(
            db,
            user_key=user_key,
            category=category,
            summary=summary,
            payload=payload,
            source_module="legacy_backfill",
            source_session_id=int(row.source_session_id) if row.source_session_id else None,
            raw_excerpt=(row.raw_excerpt or "")[:2000],
            confidence=float(row.confidence or 0.0),
            commit=False,  # batch commit at end
        )

        if outcome.action == "inserted":
            counters[f"migrated:{category}"] += 1
            counters["migrated_total"] += 1
        elif outcome.action == "refreshed":
            counters["skipped_dupe"] += 1
        elif outcome.action == "blocked":
            counters[f"blocked:{outcome.reason}"] += 1
        elif outcome.action == "validation_error":
            counters[f"validation_error:{category}"] += 1
            logging.warning(
                "validation_error for SE row id=%s category=%s: %s",
                row.id, category, outcome.reason,
            )

    db.commit()
    return dict(counters)


def _print_summary(counters: dict[str, int]) -> None:
    migrated = counters.get("migrated_total", 0)
    dupes = counters.get("skipped_dupe", 0)
    print(f"migrated {migrated} entries, skipped {dupes} dupes")
    # Verbose breakdown for audit
    print("---\ndetailed counters:")
    for key in sorted(counters.keys()):
        print(f"  {key}: {counters[key]}")


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    started = datetime.utcnow()
    db = SessionLocal()
    try:
        counters = backfill(db)
    except Exception:
        db.rollback()
        logging.exception("backfill failed; rolled back")
        return 1
    finally:
        db.close()

    elapsed = (datetime.utcnow() - started).total_seconds()
    _print_summary(counters)
    print(f"elapsed {elapsed:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
