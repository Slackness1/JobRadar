"""Auto-seed account_memory from a confirmed resume profile.

2026-05-21 v2 — **one row per experience (internship / project), not per
bullet**. The earlier per-bullet seeding flooded the archive with 20+ tiny
cards that were impossible to navigate. Now each internship / project is a
single archive card; the bullets live inside ``behavioral_hook`` as a
multi-line list and ``linked_field_paths`` references every bullet's path
(so editing any one bullet flips the row's ``needs_resync``).

  Each seeded row:
    - category = "experience"
    - summary  = "公司 · 角色" (短索引;archive 卡片标题)
    - payload.behavioral_hook = "公司 · 角色 (起 - 止)\n- bullet1\n- bullet2 ..."
    - source_module = "parser_seed"
    - confidence = 0.6  — lower than chat-confirmed (1.0) so coach can
      supersede with higher-confidence STAR detail
    - linked_field_paths = [all the bullets' paths] — Plan 1 resync flips
      this row stale if ANY linked bullet changes
    - linked_track = active_track at seed time
    - linked_job_id = ''  (track-level, not job-specific)
    - user_confirmed = False (this came from your resume; coach will help
      us deepen it)

Dedupe is automatic: dispatcher checks summary_hash uniqueness per user_key,
so re-uploading the same resume yields ``refreshed`` actions, not duplicates.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


def seed_memory_from_profile(
    db: Session,
    *,
    user_key: str,
    session_id: int,
    profile: dict[str, Any],
    active_track: str = '',
) -> dict[str, int]:
    """Seed experience rows from internship + project bullets.

    Returns a counter dict ``{inserted, refreshed, skipped, errors,
    unarchived}``. Failures are logged and swallowed — seeding is
    best-effort and must not block the confirm flow.

    2026-05-21: when re-uploading a resume, dispatcher dedupes by
    summary_hash and respects the user's prior archive state. That meant
    a student who once deleted an entry and re-uploads the same resume
    would see an empty archive. For parser_seed specifically we
    un-archive the matched row — re-uploading is a strong signal the
    student wants the entry back.
    """
    from app.services.memory.dispatcher import write_memory
    from app.models import AccountMemory
    counters = {
        "inserted": 0,
        "refreshed": 0,
        "skipped": 0,
        "errors": 0,
        "unarchived": 0,
    }

    if not user_key or user_key in ("__demo__", "__guest__"):
        counters["skipped"] = -1  # reserved
        return counters
    if not isinstance(profile, dict):
        counters["skipped"] = -2
        return counters

    # (summary, behavioral_hook_text, list_of_field_paths) per experience
    rows_to_seed: list[tuple[str, str, list[str]]] = []

    def _date_range(item: dict) -> str:
        s = str(item.get("start_date") or "").strip()
        e = str(item.get("end_date") or "").strip()
        if s and e:
            return f"({s} - {e})"
        if s:
            return f"({s} -)"
        return ""

    for i, intern in enumerate(profile.get("internships") or []):
        if not isinstance(intern, dict):
            continue
        company = str(intern.get("company") or "").strip()
        role = str(intern.get("role") or "").strip()
        head = " · ".join(p for p in (company, role) if p) or f"实习 {i + 1}"
        date_str = _date_range(intern)
        summary = head if not date_str else f"{head} {date_str}"
        bullet_lines: list[str] = []
        field_paths: list[str] = []
        for j, bullet in enumerate(intern.get("bullets") or []):
            text = str(bullet or "").strip()
            if not text:
                continue
            bullet_lines.append(f"- {text}")
            field_paths.append(f"internships.{i}.bullets.{j}")
        if not bullet_lines:
            continue
        # behavioral_hook holds the full body — archive card expands to
        # show this; 200-char cap is just summary, not body.
        hook = head + ("\n" + "\n".join(bullet_lines))
        rows_to_seed.append((summary, hook, field_paths))

    for i, proj in enumerate(profile.get("projects") or []):
        if not isinstance(proj, dict):
            continue
        name = str(proj.get("name") or proj.get("role") or "").strip() or f"项目 {i + 1}"
        date_str = _date_range(proj)
        summary = f"项目: {name}" + (f" {date_str}" if date_str else "")
        bullet_lines: list[str] = []
        field_paths: list[str] = []
        for j, bullet in enumerate(proj.get("bullets") or []):
            text = str(bullet or "").strip()
            if not text:
                continue
            bullet_lines.append(f"- {text}")
            field_paths.append(f"projects.{i}.bullets.{j}")
        if not bullet_lines:
            continue
        hook = f"项目: {name}" + ("\n" + "\n".join(bullet_lines))
        rows_to_seed.append((summary, hook, field_paths))

    if not rows_to_seed:
        return counters

    for summary, hook, field_paths in rows_to_seed:
        try:
            outcome = write_memory(
                db,
                user_key=user_key,
                category="experience",
                summary=summary,
                payload={
                    "behavioral_hook": hook,
                    "star_dimensions": [],
                    "quantified": {},
                    "evidence_ids": [],
                },
                source_module="parser_seed",
                source_session_id=session_id,
                raw_excerpt=hook[:2000],
                confidence=0.6,
                # confidence < 0.85 so auto_confirm stays False
                auto_confirm_threshold=0.85,
                linked_field_paths=field_paths,
                linked_track=active_track,
                linked_job_id="",
            )
            if outcome.action == "inserted":
                counters["inserted"] += 1
            elif outcome.action == "refreshed":
                counters["refreshed"] += 1
                # Re-uploading a resume = strong signal student wants this
                # entry to be visible again. Un-archive if dispatcher had it
                # archived (dispatcher itself "respects user decision" and
                # won't auto-unarchive — for general writes that's right,
                # but parser_seed is different: the user IS the one bringing
                # it back by re-uploading).
                row = outcome.row
                if row is not None and bool(getattr(row, "is_archived", False)):
                    row.is_archived = False
                    db.commit()
                    counters["unarchived"] += 1
            elif outcome.action == "blocked":
                counters["skipped"] += 1
            else:
                counters["errors"] += 1
        except Exception:  # noqa: BLE001 — seeding never blocks confirm
            counters["errors"] += 1
            logger.exception(
                "parser_seed failed: user_key=%s summary=%s", user_key, summary
            )
    return counters
