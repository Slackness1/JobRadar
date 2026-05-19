#!/usr/bin/env python3
"""Submit one student answer → runs process_turn_synchronous → returns next question.

Usage:
  python answer_turn.py "<student answer text>"

Reads config from CONFIG_FILE (created by seed_interview.py).
Looks up the latest open turn (turn with empty user_answer), uses its index as prev_turn_index.

Prints JSON with:
  - prev_turn_index, prev_question, prev_answer
  - next_turn_index, next_question, next_source ('skeleton'|'follow_up'|'end')
  - score: {overall, hits, misses, bonuses}   ← from prev turn after score_task ran
  - reference_answer (if available)
"""
from __future__ import annotations

import json
import sys

from _common import bootstrap_context_registry  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import InterviewTurn  # noqa: E402
from app.services.interview.llm_helpers import build_interview_llm_client  # noqa: E402
from app.services.interview.orchestrator import process_turn_synchronous  # noqa: E402

from seed_interview import CONFIG_FILE, TURN_LOG_FILE  # noqa: E402


def _load_config() -> dict:
    if not CONFIG_FILE.exists():
        raise SystemExit(f"config file missing: {CONFIG_FILE}. Run seed_interview.py first.")
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "missing arg: student answer"}), file=sys.stderr)
        return 2
    answer = sys.argv[1].strip()
    if not answer:
        print(json.dumps({"error": "empty answer"}), file=sys.stderr)
        return 2

    cfg = _load_config()
    bootstrap_context_registry()
    llm = build_interview_llm_client()

    db = SessionLocal()
    try:
        # Find the most recent open turn (no user_answer yet)
        open_turn = (
            db.query(InterviewTurn)
            .filter(
                InterviewTurn.session_id == cfg["interview_session_id"],
                InterviewTurn.user_answer == "",
            )
            .order_by(InterviewTurn.turn_index.asc())
            .first()
        )
        if open_turn is None:
            print(json.dumps({"error": "no open turn — interview already complete"}), file=sys.stderr)
            return 3
        prev_turn_index = int(open_turn.turn_index)
        prev_question = str(open_turn.question or "")
        prev_source = str(open_turn.question_source or "skeleton")

        # Find next index = max + 1
        max_idx = db.query(InterviewTurn).filter(
            InterviewTurn.session_id == cfg["interview_session_id"]
        ).count()
        next_turn_index = max_idx  # since indexes are 0-based and contiguous
    finally:
        db.close()

    next_q = process_turn_synchronous(
        session_id=cfg["interview_session_id"],
        user_key=cfg["user_key"],
        target_job=cfg["target_job"],
        chip=cfg["chip"],
        chip_summary=cfg["chip_summary"],
        prev_turn_index=prev_turn_index,
        prev_user_answer=answer,
        prev_asr_transcript={},
        next_turn_index=next_turn_index,
        llm=llm,
        candidate_summary=cfg.get("candidate_summary", ""),
        jd_content=cfg.get("jd_content", ""),
    )

    # Re-fetch the previous turn to read score + reference
    db = SessionLocal()
    try:
        prev_row = (
            db.query(InterviewTurn)
            .filter_by(session_id=cfg["interview_session_id"], turn_index=prev_turn_index)
            .one()
        )
        score = None
        if prev_row.score_json:
            try:
                score = json.loads(prev_row.score_json)
            except Exception:
                score = {"raw": prev_row.score_json[:300]}
        reference = str(prev_row.reference_answer or "")
    finally:
        db.close()

    rec = {
        "prev_turn_index": prev_turn_index,
        "prev_question": prev_question,
        "prev_question_source": prev_source,
        "prev_answer": answer,
        "score": score,
        "reference_answer_excerpt": reference[:400] if reference else "",
        "reference_answer_length": len(reference),
        "next_turn_index": next_turn_index,
        "next_question": next_q.question,
        "next_question_source": next_q.source,
    }

    with TURN_LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(json.dumps(rec, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
