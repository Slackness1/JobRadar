"""Tests for the interview TTS streaming contract."""
from __future__ import annotations

import json
import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import config
from app.services.interview.voice import tts


def _build_test_app() -> TestClient:
    from app.routers import interview as interview_router

    app = FastAPI()
    app.include_router(interview_router.router)
    return TestClient(app)


def test_pcm_route_exposes_stream_metadata(monkeypatch):
    from app.routers import interview as interview_router

    captured: dict[str, object] = {}

    def fake_synthesize(text, voice=None, audio_format='wav'):
        captured.update(text=text, voice=voice, audio_format=audio_format)
        return iter((b'\x00\x01', b'\x02\x03'))

    monkeypatch.setattr(interview_router, 'synthesize', fake_synthesize)
    response = _build_test_app().post(
        '/api/interview/tts?format=pcm',
        json={'text': '请介绍一下这个项目', 'voice': 'test-voice'},
    )

    assert response.status_code == 200
    assert response.content == b'\x00\x01\x02\x03'
    assert response.headers['content-type'].startswith('audio/pcm')
    assert response.headers['x-audio-sample-rate'] == str(tts.TTS_SAMPLE_RATE)
    assert response.headers['x-audio-sample-format'] == 's16le'
    assert response.headers['cache-control'] == 'no-store'
    assert captured == {
        'text': '请介绍一下这个项目',
        'voice': 'test-voice',
        'audio_format': 'pcm',
    }


def test_wav_route_remains_the_default(monkeypatch):
    from app.routers import interview as interview_router

    captured: dict[str, object] = {}

    def fake_synthesize(text, voice=None, audio_format='wav'):
        captured['audio_format'] = audio_format
        return iter((b'RIFF',))

    monkeypatch.setattr(interview_router, 'synthesize', fake_synthesize)
    response = _build_test_app().post(
        '/api/interview/tts',
        json={'text': '兼容路径'},
    )

    assert response.status_code == 200
    assert response.content == b'RIFF'
    assert response.headers['content-type'].startswith('audio/wav')
    assert captured['audio_format'] == 'wav'


def test_non_cosyvoice_pcm_fails_before_starting_a_stream(monkeypatch):
    monkeypatch.setattr(config, 'DASHSCOPE_API_KEY', 'test-key')
    monkeypatch.setattr(config, 'DASHSCOPE_TTS_MODEL', 'qwen3-tts-flash')

    with pytest.raises(tts.TTSUnavailable, match='does not support raw PCM'):
        tts.synthesize('测试', audio_format='pcm')


def test_closing_pcm_iterator_stops_the_provider_pump(monkeypatch):
    monkeypatch.setattr(config, 'DASHSCOPE_API_KEY', 'test-key')
    closed = threading.Event()
    sent_events: list[dict] = []

    class EndlessAudioSocket:
        def __init__(self):
            self.recv_count = 0

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            closed.set()

        def send(self, payload):
            sent_events.append(json.loads(payload))

        def recv(self, timeout=None):
            self.recv_count += 1
            if self.recv_count == 1:
                return json.dumps({'header': {'event': 'task-started'}})
            return b'\x00\x00' * 64

    monkeypatch.setattr(tts, 'ws_connect', lambda *args, **kwargs: EndlessAudioSocket())

    stream = tts._cosyvoice_iter('测试', 'test-voice', audio_format='pcm')
    assert next(stream)
    stream.close()

    assert closed.wait(timeout=1.0)
    run_task = sent_events[0]
    assert run_task['payload']['parameters']['format'] == 'pcm'
    assert run_task['payload']['parameters']['sample_rate'] == tts.TTS_SAMPLE_RATE
