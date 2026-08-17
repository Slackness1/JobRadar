"""Contracts for the feature-flagged LiveKit interview transport."""
from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import wave
from pathlib import Path
from types import SimpleNamespace

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy import inspect as sqlalchemy_inspect
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import config
from app.database import Base, get_db
from app.models import InterviewRealtimeSession
from app.services.interview.voice import livekit_adapters
from app.services.interview.voice.livekit_agent import AsrEvidenceBuffer, build_turn_handling
from app.services.interview.voice.livekit_session import (
    LiveKitVoiceUnavailable,
    issue_livekit_grant,
)


VOICE_FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "voice_turn"


def _enable_livekit(monkeypatch) -> None:
    monkeypatch.setattr(config, "VOICE_LIVEKIT_ENABLED", True)
    monkeypatch.setattr(config, "LIVEKIT_URL", "ws://livekit.test")
    monkeypatch.setattr(config, "LIVEKIT_API_KEY", "test-key")
    monkeypatch.setattr(
        config,
        "LIVEKIT_API_SECRET",
        "test-secret-test-secret-test-secret",
    )
    monkeypatch.setattr(config, "VOICE_LIVEKIT_TOKEN_TTL_SECONDS", 600)


def test_livekit_grant_is_short_lived_and_room_scoped(monkeypatch):
    _enable_livekit(monkeypatch)

    grant = issue_livekit_grant(
        session_id="session_12345678",
        user_key="candidate-user",
    )
    claims = jwt.decode(
        grant.token,
        config.LIVEKIT_API_SECRET,
        algorithms=["HS256"],
        options={"verify_aud": False},
    )

    assert claims["exp"] - claims["nbf"] == 600
    assert claims["video"] == {
        "roomJoin": True,
        "room": grant.room_name,
        "canPublish": True,
        "canSubscribe": True,
        "canPublishData": True,
        "canPublishSources": ["microphone"],
    }
    assert claims["roomConfig"]["maxParticipants"] == 2
    dispatch = claims["roomConfig"]["agents"][0]
    assert dispatch["agentName"] == config.VOICE_LIVEKIT_AGENT_NAME
    assert json.loads(dispatch["metadata"])["context_id"] == grant.context_id
    assert "candidate-user" not in grant.token


def test_livekit_grant_rejects_disabled_transport(monkeypatch):
    monkeypatch.setattr(config, "VOICE_LIVEKIT_ENABLED", False)

    try:
        issue_livekit_grant(session_id="session_12345678", user_key="candidate-user")
    except LiveKitVoiceUnavailable as exc:
        assert "disabled" in str(exc)
    else:
        raise AssertionError("disabled transport unexpectedly issued a grant")


def test_realtime_session_route_persists_context_and_downgrades_auto_mode(monkeypatch):
    from app.routers import interview as interview_router

    _enable_livekit(monkeypatch)
    monkeypatch.setattr(config, "VOICE_LIVEKIT_AUTOMATIC_TURNS_ENABLED", False)
    monkeypatch.setattr(config, "VOICE_LIVEKIT_ADAPTIVE_INTERRUPTION_ENABLED", False)

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(interview_router.router)
    app.dependency_overrides[get_db] = override_db
    response = TestClient(app).post(
        "/api/interview/realtime/session",
        headers={"X-Resume-User-Key": "candidate-user"},
        json={
            "session_id": "session_12345678",
            "target_job": "投行分析师",
            "jd_content": "负责行业研究和估值建模",
            "turn_mode": "automatic",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["turn_mode"] == "manual"
    assert payload["automatic_turns_available"] is False
    assert payload["interruption_mode"] == "vad"

    db = TestingSession()
    try:
        row = db.query(InterviewRealtimeSession).one()
        assert row.room_name == payload["room_name"]
        assert row.user_key == "candidate-user"
        assert row.jd_content == "负责行业研究和估值建模"
    finally:
        db.close()


def test_realtime_migration_is_safe_on_fresh_sqlite(monkeypatch):
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "f8b1d4c6e2a9_interview_realtime_voice_sessions.py"
    )
    spec = importlib.util.spec_from_file_location("jobradar_voice_migration", migration_path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(migration, "op", operations)
        migration.upgrade()
        migration.upgrade()

        inspector = sqlalchemy_inspect(connection)
        assert {
            "interview_turns",
            "interview_realtime_sessions",
            "interview_realtime_events",
        }.issubset(inspector.get_table_names())
        turn_columns = {
            column["name"] for column in inspector.get_columns("interview_turns")
        }
        assert {
            "question_heard_text",
            "question_interrupted",
            "realtime_transport",
        }.issubset(turn_columns)


def test_dashscope_stt_maps_partial_and_timed_final_events(monkeypatch):
    async def fake_asr(audio_frames, send_event, *, sample_rate):
        assert sample_rate == 16000
        frames = [frame async for frame in audio_frames]
        assert frames
        await send_event({"type": "partial", "text": "我负责"})
        await send_event(
            {"type": "final", "text": "我负责估值建模", "start_s": 0.2, "end_s": 1.4}
        )

    monkeypatch.setattr(livekit_adapters, "run_asr_session", fake_asr)

    async def collect():
        from livekit import rtc

        recognizer = livekit_adapters.DashScopeSTT().stream()
        recognizer.push_frame(
            rtc.AudioFrame(
                data=b"\x00\x00" * 160,
                sample_rate=16000,
                num_channels=1,
                samples_per_channel=160,
            )
        )
        recognizer.end_input()
        return [event async for event in recognizer]

    events = asyncio.run(collect())
    assert [event.type.value for event in events] == [
        "interim_transcript",
        "final_transcript",
    ]
    final = events[-1].alternatives[0]
    assert final.text == "我负责估值建模"
    assert (final.start_time, final.end_time) == (0.2, 1.4)


def test_dashscope_tts_pushes_pcm_and_closes_cancelled_iterator(monkeypatch):
    closed = False

    def fake_synthesize(text, voice, audio_format):
        assert (text, voice, audio_format) == ("下一题", "test-voice", "pcm")

        def chunks():
            nonlocal closed
            try:
                yield b"\x01\x02" * 64
                yield b"\x03\x04" * 64
            finally:
                closed = True

        return chunks()

    monkeypatch.setattr(livekit_adapters, "synthesize", fake_synthesize)

    async def run_tts():
        adapter = livekit_adapters.DashScopeTTS(voice="test-voice")
        async with adapter.synthesize("下一题") as stream:
            frames = [event.frame.data.tobytes() async for event in stream]
            return b"".join(frames)

    audio = asyncio.run(run_tts())

    expected = (b"\x01\x02" * 64) + (b"\x03\x04" * 64)
    assert audio.startswith(expected)
    assert set(audio[len(expected):]) <= {0}
    assert closed is True


def test_phase3_turn_policy_keeps_manual_default_and_gates_adaptive(monkeypatch):
    monkeypatch.setattr(config, "VOICE_LIVEKIT_MIN_INTERRUPTION_SECONDS", 0.55)
    monkeypatch.setattr(
        config,
        "VOICE_LIVEKIT_FALSE_INTERRUPTION_TIMEOUT_SECONDS",
        1.6,
    )
    manual = build_turn_handling(
        SimpleNamespace(turn_mode="manual", interruption_mode="vad")
    )
    automatic = build_turn_handling(
        SimpleNamespace(turn_mode="automatic", interruption_mode="adaptive")
    )

    assert manual["turn_detection"] == "manual"
    assert manual["preemptive_generation"]["enabled"] is False
    assert manual["interruption"]["mode"] == "vad"
    assert manual["interruption"]["min_words"] == 1
    assert manual["interruption"]["resume_false_interruption"] is True
    assert automatic["turn_detection"] != "manual"
    assert automatic["preemptive_generation"]["enabled"] is False
    assert automatic["interruption"]["mode"] == "adaptive"


def test_livekit_asr_evidence_preserves_optional_timing_and_normalizes_turn_origin():
    evidence = AsrEvidenceBuffer()
    evidence.add_final({"type": "final", "text": "第一句", "start_s": 12.4, "end_s": 13.1})
    evidence.add_final({"type": "final", "text": "没有时间的第二句"})
    evidence.add_final({"type": "final", "text": "第三句", "start_s": 13.5, "end_s": 14.2})

    snapshot = evidence.snapshot()
    assert snapshot is not None
    assert snapshot["audio_duration_s"] == pytest.approx(1.8)
    assert snapshot["segments"][0] == {
        "text": "第一句",
        "start_s": pytest.approx(0.0),
        "end_s": pytest.approx(0.7),
    }
    assert snapshot["segments"][1] == {"text": "没有时间的第二句"}
    assert snapshot["segments"][2] == {
        "text": "第三句",
        "start_s": pytest.approx(1.1),
        "end_s": pytest.approx(1.8),
    }
    evidence.clear()
    assert evidence.snapshot() is None


def test_phase3_audio_fixtures_are_deterministic_and_match_guard_contract(monkeypatch):
    monkeypatch.setattr(config, "VOICE_LIVEKIT_MIN_INTERRUPTION_SECONDS", 0.55)
    options = build_turn_handling(
        SimpleNamespace(turn_mode="manual", interruption_mode="vad")
    )["interruption"]
    manifest = json.loads((VOICE_FIXTURE_ROOT / "manifest.json").read_text("utf-8"))

    assert manifest["sample_rate"] == 16000
    for case in manifest["cases"]:
        path = VOICE_FIXTURE_ROOT / case["file"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == case["sha256"]
        with wave.open(str(path), "rb") as wav:
            assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (
                16000,
                1,
                2,
            )
        speech_duration = float(case.get("speech_duration_s") or 0.0)
        transcript_words = 1 if str(case.get("transcript") or "").strip() else 0
        accepted = (
            speech_duration >= options["min_duration"]
            and transcript_words >= options["min_words"]
        )
        assert accepted is case["expected_interruption"], case["file"]


def test_silero_rejects_deterministic_silence_noise_keyboard_and_cough():
    from livekit import rtc
    from livekit.agents import vad
    from livekit.plugins import silero

    nuisance_files = (
        "silence_pause.wav",
        "background_noise.wav",
        "keyboard_impulses.wav",
        "cough_like.wav",
        "short_filler.wav",
    )

    async def run_fixture(path: Path):
        detector = silero.VAD.load(
            min_speech_duration=0.08,
            min_silence_duration=0.45,
            prefix_padding_duration=0.35,
            activation_threshold=0.58,
        )
        stream = detector.stream()
        with wave.open(str(path), "rb") as wav:
            pcm = wav.readframes(wav.getnframes())
        frame_bytes = 160 * 2
        for offset in range(0, len(pcm), frame_bytes):
            frame = pcm[offset:offset + frame_bytes].ljust(frame_bytes, b"\x00")
            stream.push_frame(
                rtc.AudioFrame(
                    data=frame,
                    sample_rate=16000,
                    num_channels=1,
                    samples_per_channel=160,
                )
            )
        stream.end_input()
        return [event async for event in stream]

    async def run_all():
        return {
            name: await run_fixture(VOICE_FIXTURE_ROOT / name)
            for name in nuisance_files
        }

    results = asyncio.run(run_all())
    for name, events in results.items():
        sustained_end_events = [
            event
            for event in events
            if event.type == vad.VADEventType.END_OF_SPEECH
            and event.speech_duration >= config.VOICE_LIVEKIT_MIN_INTERRUPTION_SECONDS
        ]
        assert sustained_end_events == [], name
