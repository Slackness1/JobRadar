"""Identity spoofing must not reach another student's interview data.

`X-Resume-User-Key` is a browser-supplied header and account keys are the
enumerable form `u_<id>`. These tests pin the rule that an account key is only
honoured when the caller also presents that account's bearer session token —
otherwise anyone could set `X-Resume-User-Key: u_1` and pull down someone
else's raw answer audio, transcripts or scores.
"""
from __future__ import annotations

import io
import wave

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.database import get_db
from app.models import InterviewAudioArtifact, InterviewTurn
from app.services.auth import auth_service
from app.services.interview.voice_intelligence import CONSENT_VERSION
from tests._threadsafe_db import make_threadsafe_sessionmaker


def _wav_bytes(seconds: float = 0.8, sample_rate: int = 16000) -> bytes:
    frames = b"\x00\x00" * int(seconds * sample_rate)
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(frames)
    return output.getvalue()


def _build_app():
    from app.routers import interview as interview_router

    # Uploading kicks off the audio-analysis daemons, so sessions must not share
    # one connection with them (see tests/_threadsafe_db.py).
    TestingSession = make_threadsafe_sessionmaker("jobradar-authz-test-")

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


def _make_account(SessionLocal, email: str) -> tuple[str, str]:
    """Create a verified account plus a live session token → (user_key, token)."""
    db = SessionLocal()
    try:
        user = auth_service.create_user(db, email=email, password="pw-12345678", invite_code_id=None)
        auth_service.mark_email_verified(db, user)
        session = auth_service.create_session(db, user)
        db.commit()
        return auth_service.user_key_for(user), session.token
    finally:
        db.close()


def _upload_as_owner(client, *, token: str, session_id: str) -> str:
    response = client.post(
        "/api/interview/audio-artifacts",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "session_id": session_id,
            "turn_index": 0,
            "consent_granted": "true",
            "consent_version": CONSENT_VERSION,
            "transcript_text": "我负责 DCF 建模",
        },
        files={"audio": ("turn0.wav", _wav_bytes(), "audio/wav")},
    )
    assert response.status_code == 202, response.text
    return response.json()["id"]


def _setup_two_accounts():
    client, SessionLocal = _build_app()
    owner_key, owner_token = _make_account(SessionLocal, "owner@saif.test")
    other_key, other_token = _make_account(SessionLocal, "other@saif.test")
    session_id = "session-authz-0001"

    db = SessionLocal()
    db.add(InterviewTurn(
        session_id=session_id,
        user_key=owner_key,
        turn_index=0,
        question="请讲一个你主导的估值项目",
        user_answer="我负责 DCF 建模",
    ))
    db.commit()
    db.close()

    artifact_id = _upload_as_owner(client, token=owner_token, session_id=session_id)
    return client, SessionLocal, owner_key, owner_token, other_key, other_token, session_id, artifact_id


def test_header_alone_cannot_claim_another_users_audio():
    """No token at all + a guessed `u_<id>` header → rejected everywhere."""
    client, _, owner_key, _, _, _, session_id, artifact_id = _setup_two_accounts()
    spoof = {"X-Resume-User-Key": owner_key}

    assert client.get(f"/api/interview/audio-artifacts/{artifact_id}", headers=spoof).status_code in (401, 403)
    assert client.get(f"/api/interview/audio-artifacts/{artifact_id}/audio", headers=spoof).status_code in (401, 403)
    assert client.get(f"/api/interview/sessions/{session_id}/audio-artifacts", headers=spoof).status_code in (401, 403)
    assert client.delete(f"/api/interview/audio-artifacts/{artifact_id}", headers=spoof).status_code in (401, 403)
    assert client.get(f"/api/interview/sessions/{session_id}/turns", headers=spoof).status_code in (401, 403)


def test_logged_in_user_cannot_borrow_another_users_key():
    """A real account B, presenting B's token but A's header, stays B."""
    client, _, owner_key, _, _, other_token, session_id, artifact_id = _setup_two_accounts()
    borrowed = {"Authorization": f"Bearer {other_token}", "X-Resume-User-Key": owner_key}

    assert client.get(f"/api/interview/audio-artifacts/{artifact_id}", headers=borrowed).status_code == 403
    assert client.get(f"/api/interview/audio-artifacts/{artifact_id}/audio", headers=borrowed).status_code == 403
    assert client.delete(f"/api/interview/audio-artifacts/{artifact_id}", headers=borrowed).status_code == 403
    assert client.get(f"/api/interview/sessions/{session_id}/turns", headers=borrowed).status_code == 403
    assert client.get(f"/api/interview/sessions/{session_id}/audio-artifacts", headers=borrowed).status_code == 403


def test_spoofed_delete_leaves_the_recording_on_disk():
    """The owner's file must still exist after a spoofed delete attempt."""
    client, SessionLocal, owner_key, owner_token, _, other_token, _, artifact_id = _setup_two_accounts()

    db = SessionLocal()
    row = db.query(InterviewAudioArtifact).filter_by(id=artifact_id).one()
    storage_path = row.storage_path
    db.close()

    from pathlib import Path

    assert Path(storage_path).exists()
    client.delete(
        f"/api/interview/audio-artifacts/{artifact_id}",
        headers={"Authorization": f"Bearer {other_token}", "X-Resume-User-Key": owner_key},
    )
    assert Path(storage_path).exists(), "spoofed delete removed the owner's recording"

    # The real owner can still delete it — the guard blocks impostors, not owners.
    assert client.delete(
        f"/api/interview/audio-artifacts/{artifact_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    ).status_code == 204
    assert not Path(storage_path).exists()


def test_expired_or_bogus_token_is_401_not_a_header_fallback():
    """A dead token must fail closed rather than quietly trusting the header."""
    client, _, owner_key, _, _, _, session_id, artifact_id = _setup_two_accounts()
    dead = {"Authorization": "Bearer not-a-real-token", "X-Resume-User-Key": owner_key}

    assert client.get(f"/api/interview/audio-artifacts/{artifact_id}", headers=dead).status_code == 401
    assert client.get(f"/api/interview/sessions/{session_id}/turns", headers=dead).status_code == 401


def test_owner_with_token_keeps_full_access():
    """Regression guard: the fix must not lock the real owner out."""
    client, _, _, owner_token, _, _, session_id, artifact_id = _setup_two_accounts()
    auth = {"Authorization": f"Bearer {owner_token}"}

    assert client.get(f"/api/interview/audio-artifacts/{artifact_id}", headers=auth).status_code == 200
    assert client.get(f"/api/interview/audio-artifacts/{artifact_id}/audio", headers=auth).status_code == 200
    listed = client.get(f"/api/interview/sessions/{session_id}/audio-artifacts", headers=auth)
    assert listed.status_code == 200 and len(listed.json()) == 1
    assert client.get(f"/api/interview/sessions/{session_id}/turns", headers=auth).status_code == 200


def test_guest_uuid_keys_still_work_without_a_token():
    """Guests have no credential to present; their random UUID key stays valid."""
    client, SessionLocal = _build_app()
    guest_key = "3f2c9a4e-77b1-4d0e-9f21-6a5f0c8b1234"
    session_id = "session-guest-0001"

    db = SessionLocal()
    db.add(InterviewTurn(
        session_id=session_id, user_key=guest_key, turn_index=0,
        question="Q", user_answer="A",
    ))
    db.commit()
    db.close()

    headers = {"X-Resume-User-Key": guest_key}
    assert client.get(f"/api/interview/sessions/{session_id}/turns", headers=headers).status_code == 200
    upload = client.post(
        "/api/interview/audio-artifacts",
        headers=headers,
        data={
            "session_id": session_id,
            "turn_index": 0,
            "consent_granted": "true",
            "consent_version": CONSENT_VERSION,
            "transcript_text": "A",
        },
        files={"audio": ("turn0.wav", _wav_bytes(), "audio/wav")},
    )
    assert upload.status_code == 202, upload.text
