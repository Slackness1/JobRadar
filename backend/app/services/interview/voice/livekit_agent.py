"""Separate LiveKit Agents runtime for JobRadar mock interviews."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    TurnHandlingOptions,
    cli,
    inference,
    llm,
)
from livekit.plugins import silero

from app import config
from app.database import SessionLocal
from app.models import InterviewRealtimeEvent, InterviewRealtimeSession, InterviewTurn
from app.services.interview.voice.livekit_adapters import DashScopeSTT, DashScopeTTS

logger = logging.getLogger(__name__)


@dataclass
class AsrEvidenceBuffer:
    """Collect one committed user turn without fabricating missing timing."""

    segments: list[dict[str, Any]] = field(default_factory=list)

    def add_final(self, event: dict[str, Any]) -> None:
        text = str(event.get("text") or "").strip()
        if not text:
            return
        segment: dict[str, Any] = {"text": text}
        if event.get("start_s") is not None and event.get("end_s") is not None:
            segment["start_s"] = float(event["start_s"])
            segment["end_s"] = float(event["end_s"])
        self.segments.append(segment)

    def snapshot(self) -> dict[str, Any] | None:
        if not self.segments:
            return None
        timed = [segment for segment in self.segments if "start_s" in segment]
        origin = min((segment["start_s"] for segment in timed), default=0.0)
        normalized = []
        for segment in self.segments:
            item = {"text": segment["text"]}
            if "start_s" in segment:
                item["start_s"] = max(0.0, segment["start_s"] - origin)
                item["end_s"] = max(item["start_s"], segment["end_s"] - origin)
            normalized.append(item)
        audio_duration = max(
            (segment["end_s"] - origin for segment in timed),
            default=0.0,
        )
        return {"audio_duration_s": max(0.0, audio_duration), "segments": normalized}

    def clear(self) -> None:
        self.segments.clear()


def _dispatch_context_id(metadata: str) -> str:
    try:
        payload = json.loads(metadata or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError("invalid LiveKit dispatch metadata") from exc
    context_id = str(payload.get("context_id") or "")
    if not context_id:
        raise RuntimeError("LiveKit dispatch metadata has no context_id")
    return context_id


def _load_context(context_id: str) -> InterviewRealtimeSession:
    db = SessionLocal()
    try:
        row = db.query(InterviewRealtimeSession).filter_by(context_id=context_id).first()
        if row is None:
            raise RuntimeError("realtime interview context was not found")
        if row.expires_at < datetime.utcnow():
            row.status = "expired"
            db.commit()
            raise RuntimeError("realtime interview context has expired")
        row.status = "connected"
        row.connected_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        db.expunge(row)
        return row
    finally:
        db.close()


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _json_safe(model_dump(mode="json"))
    return str(value)


def _write_event(
    context: InterviewRealtimeSession,
    event_type: str,
    payload: dict[str, Any] | None = None,
    *,
    turn_index: int | None = None,
) -> None:
    db = SessionLocal()
    try:
        db.add(
            InterviewRealtimeEvent(
                context_id=context.context_id,
                session_id=context.session_id,
                event_type=event_type,
                turn_index=turn_index,
                payload_json=json.dumps(_json_safe(payload or {}), ensure_ascii=False),
            )
        )
        db.commit()
    except Exception:
        logger.warning("failed to write realtime event %s", event_type, exc_info=True)
        db.rollback()
    finally:
        db.close()


async def _record_event(
    context: InterviewRealtimeSession,
    event_type: str,
    payload: dict[str, Any] | None = None,
    *,
    turn_index: int | None = None,
) -> None:
    await asyncio.to_thread(
        _write_event,
        context,
        event_type,
        payload,
        turn_index=turn_index,
    )


def _mark_heard_question(
    context: InterviewRealtimeSession,
    text: str,
    interrupted: bool,
) -> None:
    db = SessionLocal()
    try:
        row = (
            db.query(InterviewTurn)
            .filter(InterviewTurn.session_id == context.session_id)
            .order_by(InterviewTurn.turn_index.desc())
            .first()
        )
        if row is None:
            return
        row.question_heard_text = text
        row.question_interrupted = interrupted
        row.realtime_transport = "livekit"
        db.commit()
    finally:
        db.close()


def _latest_question(context: InterviewRealtimeSession) -> str:
    db = SessionLocal()
    try:
        row = (
            db.query(InterviewTurn.question)
            .filter(InterviewTurn.session_id == context.session_id)
            .order_by(InterviewTurn.turn_index.desc())
            .first()
        )
        return str(row[0] or "") if row else ""
    finally:
        db.close()


def _mark_session_closed(context: InterviewRealtimeSession, status: str = "closed") -> None:
    db = SessionLocal()
    try:
        row = db.query(InterviewRealtimeSession).filter_by(context_id=context.context_id).first()
        if row is None:
            return
        row.status = status
        row.closed_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()


def _chat_messages(chat_ctx: llm.ChatContext) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for item in chat_ctx.messages():
        if item.role not in {"user", "assistant"}:
            continue
        text = item.text_content.strip()
        if not text:
            continue
        messages.append({"role": item.role, "content": text})
    return messages


class JobRadarInterviewAgent(Agent):
    def __init__(
        self,
        context: InterviewRealtimeSession,
        asr_evidence: AsrEvidenceBuffer,
    ) -> None:
        super().__init__(
            instructions=(
                "你是 JobRadar 的结构化中文模拟面试官。问题内容必须来自 JobRadar "
                "Interview Orchestrator；不要自行增加寒暄、提示词或第二个问题。"
            )
        )
        self.context = context
        self.asr_evidence = asr_evidence

    async def on_enter(self) -> None:
        self.session.generate_reply(
            instructions="请求 Interview Orchestrator 给出第一道面试题。",
            allow_interruptions=True,
        )

    async def llm_node(self, chat_ctx, tools, model_settings):
        body = {
            "target_job": self.context.target_job,
            "session_id": self.context.session_id,
            "messages": _chat_messages(chat_ctx),
            "jd_content": self.context.jd_content,
        }
        if asr_transcript := self.asr_evidence.snapshot():
            body["asr_transcript"] = asr_transcript
        timeout = httpx.Timeout(45.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{config.VOICE_LIVEKIT_BACKEND_URL}/api/interview/turn",
                headers={
                    "Content-Type": "application/json",
                    "X-Resume-User-Key": self.context.user_key,
                },
                json=body,
            ) as response:
                if response.status_code >= 400:
                    detail = (await response.aread()).decode("utf-8", errors="replace")
                    raise RuntimeError(
                        f"Interview Orchestrator returned {response.status_code}: {detail[:300]}"
                    )
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if not raw:
                        continue
                    try:
                        event = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if event.get("type") == "chunk" and event.get("delta"):
                        yield str(event["delta"])
                    elif event.get("type") == "turn_complete":
                        await _record_event(
                            self.context,
                            "turn_complete",
                            {"question": event.get("question", "")},
                            turn_index=int(event.get("turn_index") or 0),
                        )
                        self.asr_evidence.clear()


def build_turn_handling(context: InterviewRealtimeSession) -> TurnHandlingOptions:
    automatic = context.turn_mode == "automatic"
    turn_detection = inference.TurnDetector(local_fallback=True) if automatic else "manual"
    return {
        "turn_detection": turn_detection,
        "endpointing": {
            "mode": "fixed",
            "min_delay": 0.55,
            "max_delay": 3.0,
        },
        "interruption": {
            "enabled": True,
            "mode": "adaptive" if context.interruption_mode == "adaptive" else "vad",
            "min_duration": max(0.25, config.VOICE_LIVEKIT_MIN_INTERRUPTION_SECONDS),
            "min_words": 1,
            "resume_false_interruption": True,
            "false_interruption_timeout": max(
                0.5, config.VOICE_LIVEKIT_FALSE_INTERRUPTION_TIMEOUT_SECONDS
            ),
            "backchannel_boundary": (0.8, 0.8),
        },
        "preemptive_generation": {
            # /api/interview/turn persists rows, so speculative calls are unsafe.
            "enabled": False,
            "preemptive_tts": False,
            "max_speech_duration": 10.0,
            "max_retries": 2,
        },
        "user_turn_limit": {"max_duration": 180.0},
    }


def _wire_rpc(
    ctx: JobContext,
    session: AgentSession,
    context: InterviewRealtimeSession,
) -> None:
    def assert_caller(data: rtc.RpcInvocationData) -> None:
        if data.caller_identity != context.participant_identity:
            raise rtc.RpcError(1403, "caller is not the room candidate")

    @ctx.room.local_participant.register_rpc_method("jobradar.commit_user_turn")
    async def commit_user_turn(data: rtc.RpcInvocationData) -> str:
        assert_caller(data)
        transcript = await session.commit_user_turn(
            transcript_timeout=3.5,
            stt_flush_duration=0.8,
        )
        await _record_event(context, "manual_turn_committed", {"characters": len(transcript)})
        return json.dumps({"transcript": transcript}, ensure_ascii=False)

    @ctx.room.local_participant.register_rpc_method("jobradar.interrupt")
    async def interrupt(data: rtc.RpcInvocationData) -> str:
        assert_caller(data)
        await session.interrupt()
        await _record_event(context, "explicit_interruption")
        return "{}"

    @ctx.room.local_participant.register_rpc_method("jobradar.clear_user_turn")
    async def clear_user_turn(data: rtc.RpcInvocationData) -> str:
        assert_caller(data)
        session.clear_user_turn()
        await _record_event(context, "manual_turn_cleared")
        return "{}"

    @ctx.room.local_participant.register_rpc_method("jobradar.repeat_question")
    async def repeat_question(data: rtc.RpcInvocationData) -> str:
        assert_caller(data)
        question = await asyncio.to_thread(_latest_question, context)
        if not question:
            raise rtc.RpcError(1404, "there is no question to repeat")
        session.say(question, allow_interruptions=True, add_to_chat_ctx=False)
        await _record_event(context, "question_repeated", {"question": question})
        return "{}"


def _wire_observability(
    session: AgentSession,
    context: InterviewRealtimeSession,
) -> None:
    def schedule(event_type: str, payload: dict[str, Any] | None = None) -> None:
        asyncio.create_task(_record_event(context, event_type, payload))

    @session.on("agent_state_changed")
    def on_agent_state(event) -> None:
        schedule("agent_state", {"old": event.old_state, "new": event.new_state})

    @session.on("user_state_changed")
    def on_user_state(event) -> None:
        schedule("user_state", {"old": event.old_state, "new": event.new_state})

    @session.on("metrics_collected")
    def on_metrics(event) -> None:
        schedule("metric", {"metric": _json_safe(event.metrics)})

    @session.on("eot_prediction")
    def on_eot(event) -> None:
        schedule(
            "eot_prediction",
            {
                "probability": event.probability,
                "threshold": event.threshold,
                "delay": event.delay,
                "inference_duration": event.inference_duration,
            },
        )

    @session.on("overlapping_speech")
    def on_overlap(event) -> None:
        schedule(
            "overlapping_speech",
            {
                "is_interruption": event.is_interruption,
                "total_duration": event.total_duration,
                "detection_delay": event.detection_delay,
                "probability": event.probability,
            },
        )

    @session.on("agent_false_interruption")
    def on_false_interruption(event) -> None:
        schedule("false_interruption", {"resumed": event.resumed})

    @session.on("conversation_item_added")
    def on_conversation_item(event) -> None:
        item = event.item
        if getattr(item, "type", "") != "message":
            return
        role = getattr(item, "role", "")
        text = getattr(item, "text_content", "")
        interrupted = bool(getattr(item, "interrupted", False))
        schedule(
            "conversation_item",
            {"role": role, "text": text, "interrupted": interrupted},
        )
        if role == "assistant" and text:
            asyncio.create_task(
                asyncio.to_thread(_mark_heard_question, context, text, interrupted)
            )

    @session.on("error")
    def on_error(event) -> None:
        schedule("error", {"error": str(event.error), "source": type(event.source).__name__})

    @session.on("close")
    def on_close(event) -> None:
        schedule("session_closed", {"reason": str(event.reason), "error": str(event.error or "")})
        asyncio.create_task(asyncio.to_thread(_mark_session_closed, context))


def _configure_otel_exporter() -> None:
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return
    from livekit.agents.telemetry import set_tracer_provider
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(
        resource=Resource.create(
            {"service.name": os.environ.get("OTEL_SERVICE_NAME", "jobradar-voice-agent")}
        )
    )
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    set_tracer_provider(provider)


_configure_otel_exporter()


server = AgentServer(
    ws_url=config.LIVEKIT_URL or None,
    api_key=config.LIVEKIT_API_KEY or None,
    api_secret=config.LIVEKIT_API_SECRET or None,
    prometheus_port=config.VOICE_LIVEKIT_PROMETHEUS_PORT,
)


@server.rtc_session(agent_name=config.VOICE_LIVEKIT_AGENT_NAME)
async def interview_voice_session(ctx: JobContext) -> None:
    context = await asyncio.to_thread(_load_context, _dispatch_context_id(ctx.job.metadata))
    asr_evidence = AsrEvidenceBuffer()
    session = AgentSession(
        stt=DashScopeSTT(on_final=asr_evidence.add_final),
        vad=silero.VAD.load(
            min_speech_duration=0.08,
            min_silence_duration=0.45,
            prefix_padding_duration=0.35,
            activation_threshold=0.58,
        ),
        tts=DashScopeTTS(),
        turn_handling=build_turn_handling(context),
        aec_warmup_duration=1.0,
        transcription_timeout=4.0,
        user_away_timeout=30.0,
    )
    _wire_rpc(ctx, session, context)
    _wire_observability(session, context)
    await _record_event(
        context,
        "session_started",
        {
            "turn_mode": context.turn_mode,
            "interruption_mode": context.interruption_mode,
        },
    )
    await session.start(
        agent=JobRadarInterviewAgent(context, asr_evidence),
        room=ctx.room,
        record=False,
    )


def main() -> None:
    cli.run_app(server)


if __name__ == "__main__":
    main()
