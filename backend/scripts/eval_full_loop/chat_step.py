#!/usr/bin/env python3
"""One chat step: send a student message → get AI reply + memory extraction summary.

Pattern:
  python chat_step.py "<student message text>"

Reads session_id from SESSION_ID_FILE. Calls generate_chat_turn → extract_for_chat_turn.
Appends a JSON line to CHAT_LOG_FILE for later aggregation.

Prints JSON to stdout with:
  - turn_index (1-based per session)
  - student_message
  - ai_reply (assistant content)
  - ai_rewrite_options_count
  - extraction: {memory_inserted, memory_refreshed, memory_blocked, memory_validation_error, evidence_inserted, rejections}
  - current_memory_count (total live rows for this user)
  - current_memory_by_category (dict)
"""
from __future__ import annotations

import json
import sys

from _common import (  # noqa: E402
    CHAT_LOG_FILE,
    SESSION_ID_FILE,
    USER_KEY,
    bootstrap_context_registry,
)

from app.database import SessionLocal  # noqa: E402
from app.models import AccountMemory, ResumeCopilotMessage  # noqa: E402
from app.services.resume_copilot.chat import generate_chat_turn  # noqa: E402
from app.services.resume_copilot.memory.extractor import extract_for_chat_turn  # noqa: E402


def _current_memory_state(db) -> tuple[int, dict[str, int]]:
    rows = (
        db.query(AccountMemory)
        .filter(AccountMemory.user_key == USER_KEY, AccountMemory.is_archived.is_(False))
        .all()
    )
    by_cat: dict[str, int] = {}
    for r in rows:
        by_cat[r.category] = by_cat.get(r.category, 0) + 1
    return len(rows), by_cat


def main() -> int:
    if len(sys.argv) < 2:
        print(
            json.dumps({"error": "missing arg: student message"}), file=sys.stderr
        )
        return 2
    student_msg = sys.argv[1].strip()
    if not student_msg:
        print(json.dumps({"error": "empty student message"}), file=sys.stderr)
        return 2
    if not SESSION_ID_FILE.exists():
        print(
            json.dumps(
                {
                    "error": f"session_id file missing: {SESSION_ID_FILE}. Run seed_chat_session.py first."
                }
            ),
            file=sys.stderr,
        )
        return 2

    session_id = int(SESSION_ID_FILE.read_text().strip())
    bootstrap_context_registry()

    db = SessionLocal()
    try:
        prior_turn_count = (
            db.query(ResumeCopilotMessage)
            .filter(
                ResumeCopilotMessage.session_id == session_id,
                ResumeCopilotMessage.role == "user",
            )
            .count()
        )
        turn_index = prior_turn_count + 1

        # 1) AI reply (writes user + assistant message rows)
        reply = generate_chat_turn(session_id, student_msg, db)

        # 2) Memory extraction (background_task in prod; sync here for instrumentation)
        extraction = extract_for_chat_turn(
            db, session_id=session_id, user_content=student_msg
        ) or {}

        # 3) Current memory snapshot
        total, by_cat = _current_memory_state(db)

        rec = {
            "turn_index": turn_index,
            "student_message": student_msg,
            "ai_reply": reply.content,
            "ai_rewrite_options_count": len(reply.rewrite_options or []),
            "extraction": {
                "memory_inserted": extraction.get("memory_inserted", 0),
                "memory_refreshed": extraction.get("memory_refreshed", 0),
                "memory_blocked": extraction.get("memory_blocked", 0),
                "memory_validation_error": extraction.get(
                    "memory_validation_error", 0
                ),
                "evidence_inserted": extraction.get("evidence_inserted", 0),
                "rejections": (extraction.get("rejections") or [])[:5],
            },
            "current_memory_count": total,
            "current_memory_by_category": by_cat,
        }

        # Append to JSONL log
        with CHAT_LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        print(json.dumps(rec, ensure_ascii=False))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
