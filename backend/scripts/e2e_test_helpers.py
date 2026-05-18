"""端到端测试 helper — subagent 用 Python 一行命令调用。

每个 helper 把"建临时 session → 跑流程 → 返回结构化数据"封装成可调用单元,
subagent 在自己的对话内串起来用。

CLI 用法:
  PYTHONPATH=. .venv/bin/python scripts/e2e_test_helpers.py setup PROFILE_JSON PREFS_JSON USER_KEY
  PYTHONPATH=. .venv/bin/python scripts/e2e_test_helpers.py recommend SESSION_ID
  PYTHONPATH=. .venv/bin/python scripts/e2e_test_helpers.py chat SESSION_ID 'USER MSG'
  PYTHONPATH=. .venv/bin/python scripts/e2e_test_helpers.py apply SESSION_ID MSG_ID OPTION_ID
  PYTHONPATH=. .venv/bin/python scripts/e2e_test_helpers.py profile SESSION_ID
  PYTHONPATH=. .venv/bin/python scripts/e2e_test_helpers.py cleanup SESSION_ID
所有输出走 stdout 单行 JSON,subagent 解析返回值。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models import (
    ResumeConfirmedProfile,
    ResumeCopilotMessage,
    ResumeCopilotSession,
    ResumePreferenceProfile,
)
from app.schemas_resume_copilot import (
    ResumePreferencePayload,
    ResumeProfilePayload,
    ResumeRecommendationItem,
)
from app.services.resume_copilot.chat import apply_rewrite, generate_chat_turn
from app.services.resume_copilot.recommendation import recommend_jobs_for_profile


def setup_test_session(profile_json: str, prefs_json: str, user_key: str) -> dict:
    """建临时 session + 写 profile + 写 preferences。返 session_id。"""
    profile = ResumeProfilePayload.model_validate(json.loads(profile_json))
    prefs = ResumePreferencePayload.model_validate(json.loads(prefs_json))

    db = SessionLocal()
    try:
        session = ResumeCopilotSession(
            file_name="e2e_test.pdf",
            name="e2e_test",
            user_key=user_key,
            status="completed",
            extracted_text="(e2e test - synthetic)",
            is_guest=0,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        session_id = session.id

        confirmed = ResumeConfirmedProfile(
            session_id=session_id,
            profile_json=profile.model_dump_json(),
        )
        db.add(confirmed)

        pref_profile = ResumePreferenceProfile(
            session_id=session_id,
            preferences_json=prefs.model_dump_json(),
        )
        db.add(pref_profile)
        db.commit()

        return {"ok": True, "session_id": session_id}
    finally:
        db.close()


def recommend_for_session(session_id: int, ai_top_n: int = 5) -> dict:
    """跑推荐 + LLM rerank,返 top-10 item list (含 priority_letter/tier_label/audit_risks etc)。"""
    db = SessionLocal()
    try:
        confirmed = db.query(ResumeConfirmedProfile).filter(
            ResumeConfirmedProfile.session_id == session_id,
        ).first()
        if not confirmed:
            return {"ok": False, "error": "no confirmed profile"}
        pref_row = db.query(ResumePreferenceProfile).filter(
            ResumePreferenceProfile.session_id == session_id,
        ).first()
        profile = ResumeProfilePayload.model_validate(json.loads(confirmed.profile_json))
        prefs = ResumePreferencePayload.model_validate(
            json.loads(pref_row.preferences_json) if pref_row else {}
        )
        items, used_ai, fallback_reason = recommend_jobs_for_profile(
            db, profile, preferences=prefs, limit=10, ai_top_n=ai_top_n,
        )
        return {
            "ok": True,
            "used_ai": used_ai,
            "fallback_reason": fallback_reason,
            "items": [i.model_dump() for i in items[:10]],
        }
    finally:
        db.close()


def chat_turn_for_session(session_id: int, user_content: str) -> dict:
    """跑 chat 一轮,返 assistant message (含 rewrite_options + audit_risks + severity)。"""
    db = SessionLocal()
    try:
        msg_out = generate_chat_turn(session_id=session_id, user_content=user_content, db=db)
        return {
            "ok": True,
            "message": msg_out.model_dump(),
        }
    finally:
        db.close()


def apply_rewrite_for_session(session_id: int, message_id: int, option_id: str) -> dict:
    """应用 rewrite option 到 profile + 返回新 profile."""
    db = SessionLocal()
    try:
        out = apply_rewrite(
            db=db, session_id=session_id, message_id=message_id, option_id=option_id,
        )
        return {"ok": True, "profile": out.model_dump()}
    finally:
        db.close()


def get_final_profile(session_id: int) -> dict:
    """读 confirmed profile (含已 apply 的 rewrites)."""
    db = SessionLocal()
    try:
        confirmed = db.query(ResumeConfirmedProfile).filter(
            ResumeConfirmedProfile.session_id == session_id,
        ).first()
        if not confirmed:
            return {"ok": False, "error": "no profile"}
        return {"ok": True, "profile": json.loads(confirmed.profile_json)}
    finally:
        db.close()


def cleanup_session(session_id: int) -> dict:
    """删 test session 跟 cascading rows (用 cascade delete)."""
    db = SessionLocal()
    try:
        # confirmed_profile / messages / preferences 通过 FK cascade
        session = db.query(ResumeCopilotSession).filter(
            ResumeCopilotSession.id == session_id,
        ).first()
        if session:
            # 显式删 messages (CASCADE 应该会但稳一下)
            db.query(ResumeCopilotMessage).filter(
                ResumeCopilotMessage.session_id == session_id,
            ).delete(synchronize_session=False)
            db.delete(session)
            db.commit()
        return {"ok": True}
    finally:
        db.close()


def _main():
    if len(sys.argv) < 2:
        print(json.dumps({"ok": False, "error": "missing subcommand"}))
        sys.exit(1)
    cmd = sys.argv[1]
    try:
        if cmd == "setup":
            result = setup_test_session(sys.argv[2], sys.argv[3], sys.argv[4])
        elif cmd == "recommend":
            result = recommend_for_session(int(sys.argv[2]))
        elif cmd == "chat":
            result = chat_turn_for_session(int(sys.argv[2]), sys.argv[3])
        elif cmd == "apply":
            result = apply_rewrite_for_session(int(sys.argv[2]), int(sys.argv[3]), sys.argv[4])
        elif cmd == "profile":
            result = get_final_profile(int(sys.argv[2]))
        elif cmd == "cleanup":
            result = cleanup_session(int(sys.argv[2]))
        else:
            result = {"ok": False, "error": f"unknown cmd {cmd}"}
    except Exception as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(result, ensure_ascii=False, default=str))


if __name__ == "__main__":
    _main()
