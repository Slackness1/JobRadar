import json

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


def test_get_turns_returns_all_for_session():
    client, SessionLocal = _build_test_app()
    db = SessionLocal()
    db.add_all([
        InterviewTurn(session_id="s1", user_key="u1", turn_index=0, question="Q0", user_answer="A0"),
        InterviewTurn(session_id="s1", user_key="u1", turn_index=1, question="Q1", user_answer="A1"),
        InterviewTurn(session_id="other", user_key="u1", turn_index=0, question="Other"),
    ])
    db.commit()
    db.close()

    resp = client.get("/api/interview/sessions/s1/turns", headers={"X-Resume-User-Key": "u1"})
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 2
    assert rows[0]["question"] == "Q0"
    assert rows[1]["question"] == "Q1"


def test_get_turns_rejects_mismatched_user_key():
    client, SessionLocal = _build_test_app()
    db = SessionLocal()
    db.add(InterviewTurn(session_id="s2", user_key="owner-A", turn_index=0, question="Q0"))
    db.commit()
    db.close()

    resp = client.get("/api/interview/sessions/s2/turns", headers={"X-Resume-User-Key": "owner-B"})
    assert resp.status_code == 403


def test_get_turns_returns_empty_list_for_unknown_session():
    client, _ = _build_test_app()
    resp = client.get("/api/interview/sessions/nonexistent/turns", headers={"X-Resume-User-Key": "u1"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_latest_score_returns_most_recent_scored_turn():
    client, SessionLocal = _build_test_app()
    db = SessionLocal()
    score = json.dumps({"overall": 70, "hits": [], "misses": ["量化"], "bonuses": []})
    db.add_all([
        InterviewTurn(session_id="s3", user_key="u1", turn_index=0, question="Q0", score_json=score),
        InterviewTurn(session_id="s3", user_key="u1", turn_index=1, question="Q1"),  # not scored
    ])
    db.commit()
    db.close()

    resp = client.get(
        "/api/interview/sessions/s3/turns/latest-score",
        headers={"X-Resume-User-Key": "u1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["turn_index"] == 0
    assert "量化" in data["hint"]


def test_latest_score_returns_null_when_no_scored_turn():
    client, SessionLocal = _build_test_app()
    db = SessionLocal()
    db.add(InterviewTurn(session_id="s4", user_key="u1", turn_index=0, question="Q0"))
    db.commit()
    db.close()

    resp = client.get(
        "/api/interview/sessions/s4/turns/latest-score",
        headers={"X-Resume-User-Key": "u1"},
    )
    assert resp.status_code == 200
    assert resp.json() is None


def test_latest_score_rejects_mismatched_user_key():
    client, SessionLocal = _build_test_app()
    db = SessionLocal()
    db.add(InterviewTurn(session_id="s5", user_key="owner-A", turn_index=0, question="Q0"))
    db.commit()
    db.close()

    resp = client.get(
        "/api/interview/sessions/s5/turns/latest-score",
        headers={"X-Resume-User-Key": "owner-B"},
    )
    assert resp.status_code == 403


def test_turns_payload_carries_voice_facts_v2_with_provenance():
    """The report reads voice-facts-v2, so /turns must serve it per turn."""
    client, SessionLocal = _build_test_app()
    db = SessionLocal()
    db.add(InterviewTurn(
        session_id="s-facts", user_key="u1", turn_index=0,
        question="请讲一个你主导的估值项目", user_answer="我负责 DCF 建模",
        asr_transcript=json.dumps({
            "audio_duration_s": 24.0,
            "segments": [
                {"start_s": 0.5, "end_s": 9.0, "text": "嗯，我负责估值建模"},
                {"start_s": 12.0, "end_s": 20.0, "text": "复盘时发现假设太乐观"},
            ],
        }),
    ))
    db.commit()
    db.close()

    resp = client.get("/api/interview/sessions/s-facts/turns", headers={"X-Resume-User-Key": "u1"})
    assert resp.status_code == 200
    facts = resp.json()[0]["voice_facts"]
    assert facts["version"] == "voice-facts-v2"

    pause = facts["metrics"]["pause_count"]
    assert pause["source"] == "asr_transcript"
    assert pause["quality"] == "degraded"          # no consented audio for this turn
    assert pause["definition"].startswith("asr_sentence_gaps_over_")
    assert facts["metrics"]["filler_count"]["value"] == 1
    assert facts["filler_positions"][0]["token"] == "嗯"

    # System-tuning metrics and pitch must not reach the student payload.
    body = resp.text
    for banned in ("stt_final_latency_ms", "pitch", "confidence"):
        assert banned not in body


def test_turns_payload_prefers_consented_audio_over_asr_timing():
    client, SessionLocal = _build_test_app()
    from app.models import InterviewAudioArtifact
    from datetime import datetime, timedelta

    db = SessionLocal()
    db.add(InterviewTurn(
        session_id="s-audio", user_key="u1", turn_index=0, question="Q", user_answer="A",
        asr_transcript=json.dumps({
            "audio_duration_s": 24.0,
            "segments": [
                {"start_s": 0.5, "end_s": 9.0, "text": "第一段"},
                {"start_s": 12.0, "end_s": 20.0, "text": "第二段"},
            ],
        }),
    ))
    now = datetime.utcnow()
    db.add(InterviewAudioArtifact(
        id="artifact-facts-1", session_id="s-audio", turn_index=0, user_key="u1",
        consent_version="v1", consented_at=now, storage_path="", sha256="", byte_size=1,
        sample_rate=16000, channels=1, duration_seconds=24.0, status="ready",
        analyzer_version="voice-facts-v1",
        features_json=json.dumps({
            "speech": {"first_speech_ms": 640, "speech_duration_seconds": 18.0},
            "pauses": {"count": 4, "total_seconds": 3.2, "max_seconds": 1.1},
            "delivery": {"articulation_cpm": 271},
            "energy": {"mean_dbfs": -21.0, "dynamic_range_db": 17.0, "clipping_ratio": 0.0},
            "pitch": {"median_hz": 180.0},
        }),
        quality_flags_json="[]",
        expires_at=now + timedelta(days=7), created_at=now, updated_at=now,
    ))
    db.commit()
    db.close()

    resp = client.get("/api/interview/sessions/s-audio/turns", headers={"X-Resume-User-Key": "u1"})
    assert resp.status_code == 200
    facts = resp.json()[0]["voice_facts"]
    assert facts["metrics"]["pause_count"]["value"] == 4
    assert facts["metrics"]["pause_count"]["source"] == "audio_artifact"
    assert facts["metrics"]["articulation_cpm"]["value"] == 271
    assert facts["metrics"]["response_start_ms"]["value"] == 640
