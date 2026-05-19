#!/usr/bin/env python3
"""Seed a ResumeCopilotSession + ConfirmedProfile for the touyan_mid persona.

- Resets any prior session/account_memory for USER_KEY (idempotent re-runs OK)
- Loads persona JSON → loads `persona["resume"]` as the confirmed profile
- Prints the new session_id to stdout AND writes it to SESSION_ID_FILE

Usage:
  cd backend && PYTHONPATH=. .venv/bin/python scripts/eval_full_loop/seed_chat_session.py
"""
from __future__ import annotations

import json
import sys

from _common import (  # noqa: E402  (local import after env bootstrap)
    CHAT_LOG_FILE,
    PERSONA_PATH,
    SESSION_ID_FILE,
    USER_KEY,
)

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    AccountMemory,
    ResumeConfirmedProfile,
    ResumeCopilotMessage,
    ResumeCopilotSession,
    ResumePreferenceProfile,
)


def main() -> int:
    persona = json.loads(PERSONA_PATH.read_text(encoding="utf-8"))
    profile = persona["resume"]
    name = profile["basic_info"].get("name", "学生")

    db = SessionLocal()
    try:
        # Clean any prior run
        old_sessions = (
            db.query(ResumeCopilotSession)
            .filter(ResumeCopilotSession.user_key == USER_KEY)
            .all()
        )
        for s in old_sessions:
            # cascade should handle ResumeConfirmedProfile + ResumePreferenceProfile + messages
            db.delete(s)
        db.query(AccountMemory).filter(AccountMemory.user_key == USER_KEY).delete()
        db.commit()

        sess = ResumeCopilotSession(
            user_key=USER_KEY,
            file_name=f"{persona['scenario_id']}_persona.pdf",
            name=name,
            status="ready",
            extracted_text=f"(persona-driven synthetic session for {persona['scenario_id']})",
        )
        db.add(sess)
        db.commit()
        db.refresh(sess)
        session_id = int(sess.id)

        confirmed = ResumeConfirmedProfile(
            session_id=session_id,
            profile_json=json.dumps(profile, ensure_ascii=False),
        )
        db.add(confirmed)

        # Pre-seed minimal preferences so PURPOSE_CHAT path doesn't crash
        prefs = {
            "preferred_tracks": persona.get("eval_anchors", {}).get(
                "expected_strong_match_tracks", []
            ),
            "preferred_locations": [profile["basic_info"].get("location", "")]
            if profile["basic_info"].get("location")
            else [],
            "preferred_company_categories": [],
        }
        db.add(
            ResumePreferenceProfile(
                session_id=session_id,
                preferences_json=json.dumps(prefs, ensure_ascii=False),
                all_skipped=0,
            )
        )
        db.commit()

        SESSION_ID_FILE.write_text(str(session_id))
        # Reset chat log file
        if CHAT_LOG_FILE.exists():
            CHAT_LOG_FILE.unlink()
        CHAT_LOG_FILE.touch()

        print(
            json.dumps(
                {
                    "session_id": session_id,
                    "user_key": USER_KEY,
                    "student_name": name,
                    "session_id_file": str(SESSION_ID_FILE),
                    "chat_log_file": str(CHAT_LOG_FILE),
                },
                ensure_ascii=False,
            )
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
