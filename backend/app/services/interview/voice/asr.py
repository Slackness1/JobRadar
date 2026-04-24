"""DashScope (阿里云百炼) Paraformer / Fun-ASR realtime proxy.

Client sends raw PCM 16kHz/16-bit/mono frames over our WebSocket; we open
our own WebSocket to DashScope, wrap in their duplex streaming protocol,
and stream transcript events back to the client.

Events emitted to the browser:
    {"type": "started"}
    {"type": "partial", "text": "..."}       # interim hypothesis
    {"type": "final",   "text": "..."}       # finalized sentence
    {"type": "completed"}
    {"type": "error",   "message": "..."}

DashScope protocol reference:
    https://help.aliyun.com/zh/model-studio/paraformer-real-time-speech-recognition
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable

import websockets

from app import config

logger = logging.getLogger(__name__)

_GATEWAY = 'wss://dashscope.aliyuncs.com/api-ws/v1/inference/'


class AsrUnavailable(RuntimeError):
    pass


def _run_task_message(task_id: str, sample_rate: int) -> str:
    return json.dumps({
        'header': {
            'action': 'run-task',
            'task_id': task_id,
            'streaming': 'duplex',
        },
        'payload': {
            'task_group': 'audio',
            'task': 'asr',
            'function': 'recognition',
            'model': config.DASHSCOPE_ASR_MODEL,
            'parameters': {
                'sample_rate': sample_rate,
                'format': 'pcm',
            },
            'input': {},
        },
    })


def _finish_task_message(task_id: str) -> str:
    return json.dumps({
        'header': {
            'action': 'finish-task',
            'task_id': task_id,
            'streaming': 'duplex',
        },
        'payload': {'input': {}},
    })


async def run_asr_session(
    audio_frames: AsyncIterator[bytes],
    send_event: Callable[[dict], Awaitable[None]],
    *,
    sample_rate: int = 16000,
) -> None:
    """Open a DashScope ASR session, forward audio, emit events via `send_event`."""
    if not config.DASHSCOPE_API_KEY:
        raise AsrUnavailable(
            'DashScope key missing: set DASHSCOPE_API_KEY in backend/.env.local'
        )

    task_id = uuid.uuid4().hex
    last_emitted = ''  # dedupe partials that haven't changed

    try:
        async with websockets.connect(
            _GATEWAY,
            additional_headers={
                'Authorization': f'bearer {config.DASHSCOPE_API_KEY}',
                'X-DashScope-DataInspection': 'enable',
            },
            max_size=None,
            ping_interval=20,
        ) as upstream:
            await upstream.send(_run_task_message(task_id, sample_rate))

            async def pump_client_audio():
                try:
                    async for frame in audio_frames:
                        if not frame:
                            continue
                        await upstream.send(frame)
                finally:
                    try:
                        await upstream.send(_finish_task_message(task_id))
                    except websockets.ConnectionClosed:
                        pass

            async def pump_upstream_events():
                nonlocal last_emitted
                async for raw in upstream:
                    if isinstance(raw, bytes):
                        continue
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    header = msg.get('header') or {}
                    event = header.get('event')
                    payload = msg.get('payload') or {}

                    if event == 'task-started':
                        await send_event({'type': 'started'})
                        continue

                    if event == 'task-failed':
                        await send_event({
                            'type': 'error',
                            'message': header.get('error_message') or 'ASR task failed',
                        })
                        return

                    if event == 'task-finished':
                        await send_event({'type': 'completed'})
                        return

                    if event == 'result-generated':
                        sentence = (payload.get('output') or {}).get('sentence') or {}
                        text = sentence.get('text', '') or ''
                        # Paraformer v2 flags finals via sentence_end=True or end_time set
                        is_final = bool(sentence.get('sentence_end')) or bool(sentence.get('end_time'))
                        if is_final and text:
                            await send_event({'type': 'final', 'text': text})
                            last_emitted = ''
                        elif text and text != last_emitted:
                            await send_event({'type': 'partial', 'text': text})
                            last_emitted = text

            await asyncio.gather(pump_client_audio(), pump_upstream_events())
    except websockets.InvalidStatus as exc:
        raise AsrUnavailable(f'DashScope rejected connection: {exc}') from exc
    except websockets.WebSocketException as exc:
        raise AsrUnavailable(f'DashScope WebSocket error: {exc}') from exc
