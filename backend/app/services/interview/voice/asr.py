"""Aliyun NLS realtime ASR proxy.

Client sends raw PCM 16kHz/16-bit/mono frames over our WebSocket; we open
our own WebSocket to Aliyun's NLS gateway, wrap in their `SpeechTranscriber`
protocol, and stream transcript events back to the client.

Events we emit to the browser:
    {"type": "started"}
    {"type": "partial", "text": "..."}       # interim hypothesis
    {"type": "final",   "text": "..."}       # finalized sentence
    {"type": "completed"}
    {"type": "error",   "message": "..."}

Docs: https://help.aliyun.com/zh/isi/developer-reference/sdk-for-websocket
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import AsyncIterator

import websockets

from app import config
from app.services.interview.voice.token import AliyunTokenError, get_token

logger = logging.getLogger(__name__)

_GATEWAY_TEMPLATE = 'wss://nls-gateway-{region}.aliyuncs.com/ws/v1'


class AsrUnavailable(RuntimeError):
    pass


def _make_header(name: str, task_id: str) -> dict:
    return {
        'appkey': config.ALIYUN_NLS_APPKEY,
        'namespace': 'SpeechTranscriber',
        'name': name,
        'task_id': task_id,
        'message_id': uuid.uuid4().hex,
    }


async def run_asr_session(
    audio_frames: AsyncIterator[bytes],
    send_event: callable,  # type: ignore[valid-type]
    *,
    sample_rate: int = 16000,
) -> None:
    """Open an Aliyun ASR session, forward audio from `audio_frames`, send events via `send_event`."""
    if not config.ALIYUN_NLS_APPKEY:
        raise AsrUnavailable(
            'Aliyun NLS AppKey missing: set ALIYUN_NLS_APPKEY in backend/.env.local'
        )

    try:
        token = get_token()
    except AliyunTokenError as exc:
        raise AsrUnavailable(str(exc)) from exc

    region = config.ALIYUN_NLS_REGION or 'cn-shanghai'
    url = _GATEWAY_TEMPLATE.format(region=region)
    task_id = uuid.uuid4().hex

    async with websockets.connect(
        url,
        additional_headers={'X-NLS-Token': token},
        max_size=None,
        ping_interval=20,
    ) as upstream:
        # 1. Send StartTranscription
        start_msg = {
            'header': _make_header('StartTranscription', task_id),
            'payload': {
                'format': 'pcm',
                'sample_rate': sample_rate,
                'enable_intermediate_result': True,
                'enable_punctuation_prediction': True,
                'enable_inverse_text_normalization': True,
            },
        }
        await upstream.send(json.dumps(start_msg))

        async def pump_client_audio():
            try:
                async for frame in audio_frames:
                    if not frame:
                        continue
                    await upstream.send(frame)
            finally:
                # Signal end-of-audio so Aliyun flushes final result
                stop_msg = {'header': _make_header('StopTranscription', task_id)}
                try:
                    await upstream.send(json.dumps(stop_msg))
                except websockets.ConnectionClosed:
                    pass

        async def pump_upstream_events():
            async for raw in upstream:
                if isinstance(raw, bytes):
                    continue  # ASR endpoint doesn't send binary back
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                header = msg.get('header') or {}
                name = header.get('name')
                payload = msg.get('payload') or {}
                text = payload.get('result', '')

                if name == 'TranscriptionStarted':
                    await send_event({'type': 'started'})
                elif name == 'TranscriptionResultChanged':
                    await send_event({'type': 'partial', 'text': text})
                elif name == 'SentenceEnd':
                    await send_event({'type': 'final', 'text': text})
                elif name == 'TranscriptionCompleted':
                    await send_event({'type': 'completed'})
                    return
                elif header.get('status') and header['status'] >= 40000000:
                    await send_event({
                        'type': 'error',
                        'message': header.get('status_text') or 'Aliyun ASR error',
                    })
                    return

        await asyncio.gather(pump_client_audio(), pump_upstream_events())
