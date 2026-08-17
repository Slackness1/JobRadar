"""Regression tests for ASR finalization and timestamp propagation."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services.interview.voice.asr import _final_event


def _build_test_app():
    from app.routers import interview as interview_router

    app = FastAPI()
    app.include_router(interview_router.router)
    return TestClient(app)


def test_asr_final_event_preserves_provider_millisecond_timestamps():
    event = _final_event(
        "这是最终识别结果",
        {"begin_time": 250, "end_time": 1430},
    )
    assert event == {
        "type": "final",
        "text": "这是最终识别结果",
        "start_s": 0.25,
        "end_s": 1.43,
    }


def test_asr_final_event_omits_incomplete_timestamps():
    event = _final_event("这是最终识别结果", {"end_time": 1430})
    assert event == {"type": "final", "text": "这是最终识别结果"}


def test_asr_stop_keeps_socket_open_until_final_and_completed(monkeypatch):
    """The browser must receive the last ASR sentence after it sends stop."""
    client = _build_test_app()

    async def fake_run_asr_session(audio_frames, send_event):
        async for _frame in audio_frames:
            pass
        await send_event({
            "type": "final",
            "text": "这是最终识别结果",
            "start_s": 0.2,
            "end_s": 1.4,
        })
        await send_event({"type": "completed"})

    monkeypatch.setattr(
        "app.routers.interview.run_asr_session",
        fake_run_asr_session,
    )

    with client.websocket_connect("/api/interview/asr") as websocket:
        websocket.send_json({"action": "stop"})
        assert websocket.receive_json() == {
            "type": "final",
            "text": "这是最终识别结果",
            "start_s": 0.2,
            "end_s": 1.4,
        }
        assert websocket.receive_json() == {"type": "completed"}
