"""LiveKit Agents adapters for JobRadar's existing DashScope speech services."""
from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator
from typing import Any, Callable

from livekit.agents import (
    APIConnectOptions,
    DEFAULT_API_CONNECT_OPTIONS,
    NOT_GIVEN,
    NotGivenOr,
    stt,
    tts,
)

from app import config
from app.services.interview.voice.asr import run_asr_session
from app.services.interview.voice.tts import TTS_SAMPLE_RATE, synthesize


def _next_chunk(stream: Iterator[bytes]) -> bytes | None:
    try:
        return next(stream)
    except StopIteration:
        return None


class DashScopeSTT(stt.STT):
    """Expose Paraformer realtime transcripts as LiveKit speech events."""

    def __init__(self, *, on_final: Callable[[dict[str, Any]], None] | None = None) -> None:
        super().__init__(
            capabilities=stt.STTCapabilities(
                streaming=True,
                interim_results=True,
                aligned_transcript="chunk",
                offline_recognize=False,
            )
        )
        self._on_final = on_final

    @property
    def model(self) -> str:
        return config.DASHSCOPE_ASR_MODEL

    @property
    def provider(self) -> str:
        return "dashscope"

    async def _recognize_impl(self, buffer, *, language=NOT_GIVEN, conn_options):
        raise NotImplementedError("DashScopeSTT supports streaming recognition only")

    def stream(
        self,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> stt.RecognizeStream:
        return _DashScopeRecognizeStream(
            stt=self,
            conn_options=conn_options,
            sample_rate=16000,
            on_final=self._on_final,
        )


class _DashScopeRecognizeStream(stt.RecognizeStream):
    def __init__(self, *, on_final, **kwargs) -> None:
        super().__init__(**kwargs)
        self._on_final = on_final

    async def _run(self) -> None:
        request_id = uuid.uuid4().hex

        async def audio_frames():
            async for item in self._input_ch:
                if isinstance(item, self._FlushSentinel):
                    continue
                yield item.data.tobytes()

        async def send_event(event: dict[str, Any]) -> None:
            event_type = event.get("type")
            text = str(event.get("text") or "").strip()
            if event_type == "error":
                raise RuntimeError(str(event.get("message") or "DashScope ASR failed"))
            if not text:
                return

            data = stt.SpeechData(
                language="zh-CN",
                text=text,
                start_time=float(event.get("start_s") or 0.0),
                end_time=float(event.get("end_s") or 0.0),
            )
            if event_type == "partial":
                speech_type = stt.SpeechEventType.INTERIM_TRANSCRIPT
            elif event_type == "final":
                speech_type = stt.SpeechEventType.FINAL_TRANSCRIPT
                if self._on_final is not None:
                    self._on_final(dict(event))
            else:
                return
            self._event_ch.send_nowait(
                stt.SpeechEvent(
                    type=speech_type,
                    request_id=request_id,
                    alternatives=[data],
                )
            )

        await run_asr_session(audio_frames(), send_event, sample_rate=16000)


class DashScopeTTS(tts.TTS):
    """Stream CosyVoice PCM chunks into LiveKit's audio output track."""

    def __init__(self, *, voice: str | None = None) -> None:
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False, aligned_transcript=False),
            sample_rate=TTS_SAMPLE_RATE,
            num_channels=1,
        )
        self._voice = voice

    @property
    def model(self) -> str:
        return config.DASHSCOPE_TTS_MODEL

    @property
    def provider(self) -> str:
        return "dashscope"

    def synthesize(
        self,
        text: str,
        *,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> tts.ChunkedStream:
        return _DashScopeChunkedStream(
            tts=self,
            input_text=text,
            conn_options=conn_options,
            voice=self._voice,
        )


class _DashScopeChunkedStream(tts.ChunkedStream):
    def __init__(self, *, voice: str | None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._voice = voice

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        output_emitter.initialize(
            request_id=uuid.uuid4().hex,
            sample_rate=TTS_SAMPLE_RATE,
            num_channels=1,
            mime_type="audio/pcm",
            stream=False,
        )
        stream = await asyncio.to_thread(
            synthesize,
            self._input_text,
            self._voice,
            "pcm",
        )
        try:
            while True:
                chunk = await asyncio.to_thread(_next_chunk, stream)
                if chunk is None:
                    break
                if chunk:
                    output_emitter.push(chunk)
            output_emitter.flush()
        finally:
            close = getattr(stream, "close", None)
            if close is not None:
                await asyncio.to_thread(close)
