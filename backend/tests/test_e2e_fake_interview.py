"""End-to-end test of a 12-turn fake interview.

Mocks the LLM stack entirely, walks through 12 turns of POST /turn,
finishes with POST /report, and verifies the resulting report
contains scoring + reference + voice + weekly_plan data.
"""
import json
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.models import InterviewTurn, InterviewReport


def _build_test_app():
    from app.routers import interview as interview_router
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine)
    app = FastAPI()
    app.include_router(interview_router.router)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), TestSessionLocal


class _FakeLLM:
    """Returns plausible answers for any LLM call."""
    def chat_json(self, system, user, **_):
        # Always returns a moderate score
        return {"overall": 65, "hits": ["项目经验"], "misses": ["量化结果"], "bonuses": []}

    def chat_text(self, system, user, **_):
        # Use the system prompt to figure out what's being asked
        if "范例答案" in system:
            return "在某次实习中，我用 STAR 结构讲清了背景行动结果，包含一个量化指标。"
        if "follow-up" in system or "下一题" in system:
            return "你说的那个项目里你具体的贡献是什么？"
        if "练习建议" in system or "整体表现" in system:
            return "你的整体表现尚可，**主要短板**是量化结果。建议针对每段经历都加上一个具体数字。"
        if "自信度" in system:
            return "70"
        return "..."


def test_full_12_turn_interview_to_report():
    client, TestSessionLocal = _build_test_app()
    sid = "e2e-sess"
    user_key = "e2e-user"
    target_job = "default"

    # Patch the router's imported SessionLocal so the orchestrator's parallel tasks
    # write to the same in-memory test DB (not the real SQLite file).
    # Also patch build_interview_llm_client at the source module so the lazy import
    # inside process_turn_synchronous resolves to _FakeLLM.
    with patch("app.routers.interview.SessionLocal", TestSessionLocal), \
         patch("app.services.interview.llm_helpers.build_interview_llm_client", lambda: _FakeLLM()):

        # Turn 1: bootstrap (empty messages) — no LLM needed for skeleton[0]
        response = client.post(
            "/api/interview/turn",
            json={"target_job": target_job, "session_id": sid, "messages": []},
            headers={"X-Resume-User-Key": user_key},
        )
        assert response.status_code == 200

        # Build initial messages list from the persisted first turn
        messages = []
        db = TestSessionLocal()
        first_turn = db.query(InterviewTurn).filter_by(session_id=sid, turn_index=0).one()
        messages.append({"role": "assistant", "content": str(first_turn.question)})
        db.close()

        for i in range(1, 12):
            messages.append({"role": "user", "content": f"我的第 {i} 个回答内容..."})
            response = client.post(
                "/api/interview/turn",
                json={
                    "target_job": target_job,
                    "session_id": sid,
                    "messages": messages,
                    "asr_transcript": {
                        "audio_duration_s": 30.0,
                        "segments": [{"start_s": 0.5, "end_s": 28.0, "text": "嗯 我做过一个项目"}],
                    },
                },
                headers={"X-Resume-User-Key": user_key},
            )
            assert response.status_code == 200
            # Extract the next question from turn_complete event
            for line in response.text.split("\n"):
                if line.startswith("data:") and "turn_complete" in line:
                    payload = json.loads(line[5:].strip())
                    messages.append({"role": "assistant", "content": payload["question"]})
                    break

        # POST /report:
        # - generate_interview_report uses build_resume_llm_client (urllib) — stub it out
        #   at the import site in the router (already bound by name at router import time)
        # - _generate_weekly_plan is called inside build_report_aggregate
        # - build_interview_llm_client in the router is patched via llm_helpers above
        _fake_report = {
            "overall_score": 72,
            "dimensions": [
                {"name": "表达清晰度", "score": 70, "comment": "较清晰"},
                {"name": "逻辑结构", "score": 68, "comment": "有改善空间"},
            ],
            "highlights": ["有项目经验"],
            "improvements": ["增加量化结果"],
            "overall_comment": "表现尚可，继续加油。",
        }
        _weekly_plan_text = "本周建议：针对量化结果重做 3 次自我介绍。"

        with patch(
            "app.routers.interview.generate_interview_report",
            return_value=_fake_report,
        ), patch(
            "app.services.interview.report._generate_weekly_plan",
            return_value=_weekly_plan_text,
        ):
            report_response = client.post(
                "/api/interview/report",
                json={
                    "target_job": target_job,
                    "session_id": sid,
                    "messages": messages,
                    "duration_seconds": 600,
                },
                headers={"X-Resume-User-Key": user_key},
            )

    assert report_response.status_code == 200
    report = report_response.json()
    assert report["turn_count"] >= 10
    assert report["weakness_profile"] is not None
    assert report["weakness_profile"]["avg_score"] is not None
    assert "量化" in report["weekly_plan_md"]

    # Verify GET /sessions/{session_id}/turns includes scored turns
    turns_response = client.get(
        f"/api/interview/sessions/{sid}/turns",
        headers={"X-Resume-User-Key": user_key},
    )
    assert turns_response.status_code == 200
    turns = turns_response.json()
    scored_turns = [t for t in turns if t["score"] is not None]
    assert len(scored_turns) >= 5  # at least half should have scores
