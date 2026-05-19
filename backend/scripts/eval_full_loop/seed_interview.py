#!/usr/bin/env python3
"""Bootstrap a mock interview session for the touyan_mid persona.

- Clears any prior InterviewTurn for our session_id
- Inserts turn 0 with the first skeleton question
- Persists session config (chip / target_job) for later steps

Prints JSON: {session_id, user_key, first_question, target_job, chip}
"""
from __future__ import annotations

import json
import sys

from _common import (  # noqa: E402
    OUT_DIR,
    PERSONA_PATH,
    SCENARIO_ID,
    USER_KEY,
)

from app.database import SessionLocal  # noqa: E402
from app.models import InterviewTurn  # noqa: E402
from app.services.interview.adaptive import SKELETON_QUESTIONS  # noqa: E402

INTERVIEW_SESSION_ID = f"eval_interview_{SCENARIO_ID}"
TARGET_JOB = "嘉实基金管理有限公司 - 2027届校招-股票行业分析师"
CHIP = "公募基金股票行业研究"  # falls back to "default" skeleton — that's fine
CHIP_SUMMARY = "公募基金股票行业研究方向(嘉实头部)"

CONFIG_FILE = OUT_DIR / f"phase3_{SCENARIO_ID}.config.json"
TURN_LOG_FILE = OUT_DIR / f"phase3_{SCENARIO_ID}.turn_log.jsonl"


def main() -> int:
    persona = json.loads(PERSONA_PATH.read_text(encoding="utf-8"))
    jd_content = persona.get("scenario_config", {}).get("target_jd_ref", "")
    candidate_summary = persona["resume"]["basic_info"].get("name", "") + " · " + persona["resume"].get(
        "candidate_summary", ""
    )

    db = SessionLocal()
    try:
        # Clear prior turns for this session
        db.query(InterviewTurn).filter(InterviewTurn.session_id == INTERVIEW_SESSION_ID).delete()
        db.commit()

        # Insert turn 0 = first skeleton question
        skeleton = SKELETON_QUESTIONS.get(CHIP) or SKELETON_QUESTIONS["default"]
        first_q = skeleton[0]
        db.add(
            InterviewTurn(
                session_id=INTERVIEW_SESSION_ID,
                user_key=USER_KEY,
                turn_index=0,
                target_job=TARGET_JOB,
                question=first_q,
                question_source="skeleton",
                parent_turn_index=None,
            )
        )
        db.commit()

        # Persist config for subsequent steps
        config = {
            "scenario_id": SCENARIO_ID,
            "interview_session_id": INTERVIEW_SESSION_ID,
            "user_key": USER_KEY,
            "target_job": TARGET_JOB,
            "chip": CHIP,
            "chip_summary": CHIP_SUMMARY,
            "candidate_summary": candidate_summary,
            "jd_content": jd_content,
            "skeleton_count": len(skeleton),
        }
        CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=False, indent=2))
        if TURN_LOG_FILE.exists():
            TURN_LOG_FILE.unlink()
        TURN_LOG_FILE.touch()

        print(
            json.dumps(
                {
                    "interview_session_id": INTERVIEW_SESSION_ID,
                    "user_key": USER_KEY,
                    "first_question": first_q,
                    "skeleton_size": len(skeleton),
                    "target_job": TARGET_JOB,
                    "chip": CHIP,
                    "config_file": str(CONFIG_FILE),
                    "turn_log_file": str(TURN_LOG_FILE),
                },
                ensure_ascii=False,
            )
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
