"""Aliyun NLS TTS (text-to-speech) streaming client.

Uses the REST "stream/v1/tts" endpoint which returns audio bytes (MP3 by default).
We keep it synchronous and yield chunks so FastAPI can stream to the browser.

Docs: https://help.aliyun.com/zh/isi/developer-reference/restful-api-for-short-speech-synthesis
"""
from __future__ import annotations

import json
from typing import Iterator
from urllib import request as urllib_request

from app import config
from app.services.interview.voice.token import get_token

_GATEWAY = 'https://nls-gateway-{region}.aliyuncs.com/stream/v1/tts'

# Default voice: "zhixiaobai" (female, standard Mandarin). Alternatives:
# - "zhiyuan" (male, warm), "zhimiao" (female, young), "aiqi" (female, professional)
DEFAULT_VOICE = 'zhiyuan'
DEFAULT_FORMAT = 'mp3'
DEFAULT_SAMPLE_RATE = 16000


class TTSUnavailable(RuntimeError):
    pass


def synthesize(text: str, voice: str | None = None) -> Iterator[bytes]:
    """Stream synthesized audio bytes for `text`.

    Validation (missing keys, empty text) happens synchronously and raises
    TTSUnavailable before returning. The HTTP connection + streaming is in
    the inner generator.
    """
    if not config.ALIYUN_NLS_APPKEY:
        raise TTSUnavailable(
            'Aliyun NLS AppKey missing: set ALIYUN_NLS_APPKEY in backend/.env.local'
        )
    if not text.strip():
        raise TTSUnavailable('text is empty')

    token = get_token()
    url = _GATEWAY.format(region=config.ALIYUN_NLS_REGION or 'cn-shanghai')
    payload = {
        'appkey': config.ALIYUN_NLS_APPKEY,
        'text': text,
        'token': token,
        'format': DEFAULT_FORMAT,
        'sample_rate': DEFAULT_SAMPLE_RATE,
        'voice': voice or DEFAULT_VOICE,
        'volume': 50,
        'speech_rate': 0,
        'pitch_rate': 0,
    }
    req = urllib_request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    resp = urllib_request.urlopen(req, timeout=30)
    content_type = resp.headers.get('Content-Type', '')
    if 'audio' not in content_type:
        error_body = resp.read().decode('utf-8', errors='replace')
        resp.close()
        raise TTSUnavailable(f'Aliyun TTS error: {error_body}')

    def _iter():
        try:
            while True:
                chunk = resp.read(4096)
                if not chunk:
                    break
                yield chunk
        finally:
            resp.close()

    return _iter()
