"""DashScope (阿里云百炼) Qwen3-TTS client.

Two-step flow:
    1. POST text → DashScope returns an OSS audio URL (WAV)
    2. Fetch the URL and stream bytes back to our caller

Docs: https://help.aliyun.com/zh/model-studio/qwen-tts
Model list: https://help.aliyun.com/zh/model-studio/models
"""
from __future__ import annotations

import json
from typing import Iterator
from urllib import request as urllib_request

from app import config

_GENERATION_URL = 'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation'


class TTSUnavailable(RuntimeError):
    pass


def _request_audio_url(text: str, voice: str) -> str:
    if not config.DASHSCOPE_API_KEY:
        raise TTSUnavailable(
            'DashScope key missing: set DASHSCOPE_API_KEY in backend/.env.local'
        )

    payload = {
        'model': config.DASHSCOPE_TTS_MODEL,
        'input': {'text': text, 'voice': voice},
        'parameters': {},
    }
    req = urllib_request.Request(
        _GENERATION_URL,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {config.DASHSCOPE_API_KEY}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    with urllib_request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode('utf-8'))
    output = (body.get('output') or {}).get('audio') or {}
    url = output.get('url')
    if not url:
        raise TTSUnavailable(f'DashScope TTS returned no audio: {body}')
    return str(url)


def synthesize(text: str, voice: str | None = None) -> Iterator[bytes]:
    """Stream synthesized audio bytes for `text`.

    Validation (missing key, empty text, upstream error) happens synchronously
    and raises TTSUnavailable before returning. Audio bytes are streamed from
    the OSS URL returned by DashScope.
    """
    if not text.strip():
        raise TTSUnavailable('text is empty')

    effective_voice = voice or config.DASHSCOPE_TTS_VOICE
    audio_url = _request_audio_url(text, effective_voice)

    resp = urllib_request.urlopen(audio_url, timeout=30)

    def _iter():
        try:
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                yield chunk
        finally:
            resp.close()

    return _iter()
