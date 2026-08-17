from __future__ import annotations

import importlib.util
import io
import wave
import time
from threading import Event
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect as sqlalchemy_inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import config
from app.database import Base, get_db
from app.models import InterviewAudioArtifact, InterviewTurn
from app.services.interview.voice_intelligence import (
    CONSENT_VERSION,
    analyze_wav,
    cleanup_expired_audio,
    normalized_character_error_rate,
)
from app.services.interview import voice_intelligence


def _wav_bytes(*, seconds: float = 1.2, sample_rate: int = 16000) -> bytes:
    count = int(seconds * sample_rate)
    time = np.arange(count) / sample_rate
    samples = (0.18 * np.sin(2 * np.pi * 180 * time) * 32767).astype("<i2")
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(samples.tobytes())
    return output.getvalue()


def _build_app():
    from app.routers import interview as interview_router

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(interview_router.router)
    app.dependency_overrides[get_db] = override_db
    return TestClient(app), TestingSession


def _seed_turn(SessionLocal, *, session_id: str = "session-voice-123", user_key: str = "owner"):
    db = SessionLocal()
    db.add(InterviewTurn(
        session_id=session_id,
        user_key=user_key,
        turn_index=0,
        question="请介绍项目",
        user_answer="我负责估值建模",
    ))
    db.commit()
    db.close()


def _upload(client: TestClient, *, consent: bool = True, user_key: str = "owner"):
    return client.post(
        "/api/interview/audio-artifacts",
        headers={"X-Resume-User-Key": user_key},
        data={
            "session_id": "session-voice-123",
            "turn_index": "0",
            "consent_granted": "true" if consent else "false",
            "consent_version": CONSENT_VERSION,
            "transcript_text": "我负责估值建模",
        },
        files={"audio": ("answer.wav", _wav_bytes(), "audio/wav")},
    )


def _wait_for_status(client: TestClient, artifact_id: str, expected: set[str]) -> dict:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        response = client.get(
            f"/api/interview/audio-artifacts/{artifact_id}",
            headers={"X-Resume-User-Key": "owner"},
        )
        payload = response.json()
        if payload["status"] in expected:
            return payload
        time.sleep(0.02)
    raise AssertionError(f"artifact {artifact_id} did not reach {expected}")


def test_upload_requires_explicit_versioned_consent(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "VOICE_AUDIO_STORAGE_DIR", tmp_path)
    client, SessionLocal = _build_app()
    _seed_turn(SessionLocal)

    response = _upload(client, consent=False)

    assert response.status_code == 422
    assert list(tmp_path.iterdir()) == []


def test_upload_analyzes_and_binds_artifact_to_owner(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "VOICE_AUDIO_STORAGE_DIR", tmp_path)
    monkeypatch.setattr(config, "VOICE_SHADOW_ASR_ENABLED", False)
    client, SessionLocal = _build_app()
    _seed_turn(SessionLocal)

    response = _upload(client)

    assert response.status_code == 202
    artifact_id = response.json()["id"]
    payload = _wait_for_status(client, artifact_id, {"ready"})
    assert payload["status"] == "ready"
    assert payload["features"]["version"] == "voice-facts-v1"
    assert payload["features"]["speech"]["speech_duration_seconds"] > 0
    assert payload["shadow_asr"] == {"status": "disabled"}
    assert payload["replay_available"] is True

    forbidden = client.get(
        f"/api/interview/audio-artifacts/{artifact_id}",
        headers={"X-Resume-User-Key": "someone-else"},
    )
    assert forbidden.status_code == 403


def test_upload_202_does_not_wait_for_analysis(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "VOICE_AUDIO_STORAGE_DIR", tmp_path)
    release = Event()
    monkeypatch.setattr(
        voice_intelligence,
        "analyze_audio_artifact",
        lambda *_args, **_kwargs: release.wait(timeout=2),
    )
    client, SessionLocal = _build_app()
    _seed_turn(SessionLocal)

    started = time.monotonic()
    response = _upload(client)
    elapsed = time.monotonic() - started
    release.set()

    assert response.status_code == 202
    assert elapsed < 0.5


def test_delete_removes_physical_audio_and_analysis(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "VOICE_AUDIO_STORAGE_DIR", tmp_path)
    client, SessionLocal = _build_app()
    _seed_turn(SessionLocal)
    artifact_id = _upload(client).json()["id"]
    stored_files = list(tmp_path.glob("*.wav"))
    assert len(stored_files) == 1

    response = client.delete(
        f"/api/interview/audio-artifacts/{artifact_id}",
        headers={"X-Resume-User-Key": "owner"},
    )

    assert response.status_code == 204
    assert not stored_files[0].exists()
    db = SessionLocal()
    row = db.query(InterviewAudioArtifact).filter_by(id=artifact_id).one()
    assert row.status == "deleted"
    assert row.storage_path == ""
    assert row.features_json == "{}"
    db.close()


def test_expiry_cleanup_removes_only_expired_files(tmp_path):
    _, SessionLocal = _build_app()
    now = datetime.utcnow()
    expired_path = tmp_path / "expired.wav"
    live_path = tmp_path / "live.wav"
    expired_path.write_bytes(_wav_bytes())
    live_path.write_bytes(_wav_bytes())
    db = SessionLocal()
    db.add_all([
        InterviewAudioArtifact(
            id="expired", session_id="s", turn_index=0, user_key="u",
            consent_version=CONSENT_VERSION, consented_at=now,
            storage_path=str(expired_path), expires_at=now - timedelta(seconds=1),
            created_at=now, updated_at=now,
        ),
        InterviewAudioArtifact(
            id="live", session_id="s", turn_index=1, user_key="u",
            consent_version=CONSENT_VERSION, consented_at=now,
            storage_path=str(live_path), expires_at=now + timedelta(days=1),
            created_at=now, updated_at=now,
        ),
    ])
    db.commit()

    assert cleanup_expired_audio(db, now=now) == 1
    assert not expired_path.exists()
    assert live_path.exists()
    assert db.query(InterviewAudioArtifact).filter_by(id="expired").one().status == "expired"
    db.close()


def test_deterministic_analysis_and_character_error_rate(tmp_path):
    path = tmp_path / "tone.wav"
    path.write_bytes(_wav_bytes())

    first, first_flags = analyze_wav(path, transcript_text="我负责估值建模")
    second, second_flags = analyze_wav(path, transcript_text="我负责估值建模")

    assert first == second
    assert first_flags == second_flags
    assert 170 <= first["pitch"]["median_hz"] <= 190
    assert normalized_character_error_rate("我负责估值建模", "我负责估值建") == round(1 / 7, 4)


def test_audio_artifact_migration_is_idempotent_on_fresh_sqlite(monkeypatch):
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "9d4a6c2e7b10_interview_audio_artifacts.py"
    )
    spec = importlib.util.spec_from_file_location("jobradar_audio_migration", migration_path)
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
        assert "interview_audio_artifacts" in inspector.get_table_names()
        columns = {
            column["name"] for column in inspector.get_columns("interview_audio_artifacts")
        }
        assert {"consent_version", "storage_path", "features_json", "expires_at"}.issubset(columns)
