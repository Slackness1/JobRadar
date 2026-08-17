"""DashScope (阿里云百炼) TTS client.

Dispatches between two backends based on `config.DASHSCOPE_TTS_MODEL`:
  - `qwen3-tts-*`  → HTTP REST (text → OSS WAV URL → stream bytes)
  - `cosyvoice-*`  → WebSocket duplex (binary audio frames stream back)

Both paths return an Iterator[bytes]. WAV remains the compatibility default;
CosyVoice can also return raw signed 16-bit little-endian PCM for true browser
streaming.

Docs:
  Qwen3-TTS:  https://help.aliyun.com/zh/model-studio/qwen-tts
  CosyVoice:  https://help.aliyun.com/zh/model-studio/cosyvoice-websocket-api
"""
from __future__ import annotations

import json
import queue
import threading
import uuid
from typing import Iterator
from urllib import request as urllib_request

from websockets.sync.client import connect as ws_connect

from app import config

_HTTP_GENERATION_URL = 'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation'
_WS_GATEWAY = 'wss://dashscope.aliyuncs.com/api-ws/v1/inference/'
TTS_SAMPLE_RATE = 22050
_SUPPORTED_AUDIO_FORMATS = {'wav', 'pcm'}


class TTSUnavailable(RuntimeError):
    pass


# ─── Qwen3-TTS (HTTP) ──────────────────────────────────────────────────────────

def _qwen_tts_iter(text: str, voice: str) -> Iterator[bytes]:
    payload = {
        'model': config.DASHSCOPE_TTS_MODEL,
        'input': {'text': text, 'voice': voice},
        'parameters': {},
    }
    req = urllib_request.Request(
        _HTTP_GENERATION_URL,
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
        raise TTSUnavailable(f'DashScope Qwen-TTS returned no audio: {body}')

    audio_resp = urllib_request.urlopen(str(url), timeout=30)

    def _iter():
        try:
            while True:
                chunk = audio_resp.read(8192)
                if not chunk:
                    break
                yield chunk
        finally:
            audio_resp.close()

    return _iter()


# ─── CosyVoice (WebSocket duplex) ──────────────────────────────────────────────

def _cosyvoice_iter(
    text: str,
    voice: str,
    audio_format: str = 'wav',
) -> Iterator[bytes]:
    """Open a WS to DashScope, send run/continue/finish, yield received audio bytes.

    Runs the WS pump on a background thread, yielding bytes from a queue so the
    caller stays sync. On error the queue receives the exception to re-raise.
    """
    task_id = uuid.uuid4().hex
    audio_queue: queue.Queue[bytes | Exception | None] = queue.Queue(maxsize=64)
    cancelled = threading.Event()

    def _put(item: bytes | Exception | None) -> bool:
        while not cancelled.is_set():
            try:
                audio_queue.put(item, timeout=0.1)
                return True
            except queue.Full:
                continue
        return False

    def _pump():
        try:
            with ws_connect(
                _WS_GATEWAY,
                additional_headers={'Authorization': f'bearer {config.DASHSCOPE_API_KEY}'},
                max_size=None,
                open_timeout=15,
            ) as ws:
                # 1) run-task
                ws.send(json.dumps({
                    'header': {'action': 'run-task', 'task_id': task_id, 'streaming': 'duplex'},
                    'payload': {
                        'task_group': 'audio',
                        'task': 'tts',
                        'function': 'SpeechSynthesizer',
                        'model': config.DASHSCOPE_TTS_MODEL,
                        'parameters': {
                            'text_type': 'PlainText',
                            'voice': voice,
                            'format': audio_format,
                            'sample_rate': TTS_SAMPLE_RATE,
                            'volume': 50,
                            'rate': 1,
                            'pitch': 1,
                        },
                        'input': {},
                    },
                }))

                # 2) wait for task-started, then send text + finish
                started = False
                finished_sent = False
                while True:
                    if cancelled.is_set():
                        return
                    try:
                        msg = ws.recv(timeout=0.25)
                    except TimeoutError:
                        continue
                    if isinstance(msg, bytes):
                        if not _put(msg):
                            return
                        continue
                    event = json.loads(msg)
                    name = (event.get('header') or {}).get('event')
                    if name == 'task-started' and not started:
                        started = True
                        ws.send(json.dumps({
                            'header': {'action': 'continue-task', 'task_id': task_id, 'streaming': 'duplex'},
                            'payload': {'input': {'text': text}},
                        }))
                        ws.send(json.dumps({
                            'header': {'action': 'finish-task', 'task_id': task_id, 'streaming': 'duplex'},
                            'payload': {'input': {}},
                        }))
                        finished_sent = True
                    elif name == 'task-finished':
                        break
                    elif name == 'task-failed':
                        err = (event.get('header') or {}).get('error_message') or str(event)
                        raise TTSUnavailable(f'CosyVoice task-failed: {err}')

                _ = finished_sent  # silence "unused" lint
        except Exception as exc:
            _put(exc)
        finally:
            _put(None)

    threading.Thread(target=_pump, daemon=True).start()

    def _iter():
        try:
            while True:
                item = audio_queue.get()
                if item is None:
                    return
                if isinstance(item, Exception):
                    raise item
                yield item
        finally:
            cancelled.set()

    return _iter()


# ─── Public API ────────────────────────────────────────────────────────────────

def synthesize(
    text: str,
    voice: str | None = None,
    audio_format: str = 'wav',
) -> Iterator[bytes]:
    """Stream synthesized audio bytes. Validation raises upfront."""
    if not config.DASHSCOPE_API_KEY:
        raise TTSUnavailable('DashScope key missing: set DASHSCOPE_API_KEY in backend/.env.local')
    if not text.strip():
        raise TTSUnavailable('text is empty')
    if audio_format not in _SUPPORTED_AUDIO_FORMATS:
        raise TTSUnavailable(f'unsupported audio format: {audio_format}')

    effective_voice = voice or config.DASHSCOPE_TTS_VOICE
    model = config.DASHSCOPE_TTS_MODEL.lower()

    if model.startswith('cosyvoice'):
        return _cosyvoice_iter(text, effective_voice, audio_format=audio_format)
    if audio_format != 'wav':
        raise TTSUnavailable(
            f'{config.DASHSCOPE_TTS_MODEL} does not support raw PCM streaming'
        )
    return _qwen_tts_iter(text, effective_voice)
