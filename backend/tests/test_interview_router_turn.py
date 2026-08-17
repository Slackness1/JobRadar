"""Integration tests for the upgraded /api/interview/turn endpoint."""
import json
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.models import InterviewTurn


def _build_test_app():
    from app.routers import interview as interview_router

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    app = FastAPI()
    app.include_router(interview_router.router)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), SessionLocal


def _parse_sse_events(body: str):
    """Parse SSE response body into a list of {type, ...} dicts."""
    events = []
    for line in body.split("\n"):
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        if not payload:
            continue
        try:
            events.append(json.loads(payload))
        except json.JSONDecodeError:
            events.append({"type": "raw", "value": payload})
    return events


def test_first_turn_emits_chunk_and_turn_complete_for_skeleton_question(monkeypatch):
    """When messages is empty (first turn), skeleton[0] is streamed."""
    client, SessionLocal = _build_test_app()

    response = client.post(
        "/api/interview/turn",
        json={
            "target_job": "default",
            "session_id": "test-sess-1",
            "messages": [],
        },
        headers={"X-Resume-User-Key": "u1"},
    )
    assert response.status_code == 200
    events = _parse_sse_events(response.text)

    # Expect at least: chunk (with delta) + turn_complete
    assert any(e.get("type") == "chunk" for e in events)
    complete_events = [e for e in events if e.get("type") == "turn_complete"]
    assert len(complete_events) == 1
    assert complete_events[0]["turn_index"] == 0
    assert "自我介绍" in complete_events[0]["question"]

    # Verify the row was persisted
    db = SessionLocal()
    try:
        rows = db.query(InterviewTurn).filter_by(session_id="test-sess-1").all()
        assert len(rows) == 1
        assert rows[0].question_source == "skeleton"
    finally:
        db.close()


def test_subsequent_turn_runs_orchestrator(monkeypatch):
    """When messages contains prior assistant + user pairs, process_turn fires."""
    client, SessionLocal = _build_test_app()

    # Seed: pretend turn 0 already happened
    db = SessionLocal()
    db.add(InterviewTurn(
        session_id="test-sess-2", user_key="u1", turn_index=0, target_job="default",
        question="请用 1-2 分钟做个自我介绍。", question_source="skeleton",
    ))
    db.commit()
    db.close()

    captured_calls = []

    def stub_process(**kwargs):
        captured_calls.append(kwargs)
        from app.services.interview.adaptive import NextQuestion
        return NextQuestion(question="第二题：讲一段你的项目。", source="skeleton")

    monkeypatch.setattr(
        "app.routers.interview.process_turn_synchronous",
        stub_process,
    )
    asr_transcript = {
        "audio_duration_s": 28.4,
        "segments": [
            {"start_s": 0.2, "end_s": 15.5, "text": "嗯，我先介绍一下项目背景。"},
            {"start_s": 16.1, "end_s": 28.4, "text": "最后结果是转化率提升。"},
        ],
    }

    response = client.post(
        "/api/interview/turn",
        json={
            "target_job": "default",
            "session_id": "test-sess-2",
            "messages": [
                {"role": "assistant", "content": "请用 1-2 分钟做个自我介绍。"},
                {"role": "user", "content": "我叫张三，本科上交大..."},
            ],
            "asr_transcript": asr_transcript,
        },
        headers={"X-Resume-User-Key": "u1"},
    )
    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    assert any("第二题" in e.get("delta", "") for e in events if e.get("type") == "chunk")
    assert len(captured_calls) == 1
    assert captured_calls[0]["session_id"] == "test-sess-2"
    assert captured_calls[0]["prev_user_answer"] == "我叫张三，本科上交大..."
    assert captured_calls[0]["prev_asr_transcript"] == asr_transcript


def test_turn_rejects_half_timed_asr_segment():
    client, _ = _build_test_app()

    response = client.post(
        "/api/interview/turn",
        json={
            "target_job": "default",
            "session_id": "invalid-asr",
            "messages": [],
            "asr_transcript": {
                "audio_duration_s": 3,
                "segments": [{"start_s": 0.5, "text": "缺少结束时间"}],
            },
        },
        headers={"X-Resume-User-Key": "u1"},
    )

    assert response.status_code == 422


def test_turn_endpoint_records_user_key():
    client, SessionLocal = _build_test_app()
    client.post(
        "/api/interview/turn",
        json={"target_job": "default", "session_id": "uk1", "messages": []},
        headers={"X-Resume-User-Key": "owner-A"},
    )
    db = SessionLocal()
    try:
        row = db.query(InterviewTurn).filter_by(session_id="uk1").one()
        assert row.user_key == "owner-A"
    finally:
        db.close()
