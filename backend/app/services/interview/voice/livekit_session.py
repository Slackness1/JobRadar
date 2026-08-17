"""Room-scoped LiveKit grants and short-lived interview context helpers."""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from livekit import api

from app import config


_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,80}$")


class LiveKitVoiceUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class LiveKitGrant:
    context_id: str
    room_name: str
    participant_identity: str
    token: str
    expires_at: datetime


def assert_livekit_configured() -> None:
    if not config.VOICE_LIVEKIT_ENABLED:
        raise LiveKitVoiceUnavailable("LiveKit voice transport is disabled")
    missing = [
        name
        for name, value in (
            ("LIVEKIT_URL", config.LIVEKIT_URL),
            ("LIVEKIT_API_KEY", config.LIVEKIT_API_KEY),
            ("LIVEKIT_API_SECRET", config.LIVEKIT_API_SECRET),
        )
        if not value
    ]
    if missing:
        raise LiveKitVoiceUnavailable(
            f"LiveKit voice transport is not configured: {', '.join(missing)}"
        )


def validate_realtime_session_id(session_id: str) -> str:
    value = session_id.strip()
    if not _SESSION_ID_RE.fullmatch(value):
        raise ValueError("session_id must contain 8-80 letters, digits, underscores or dashes")
    return value


def room_name_for_session(session_id: str, context_id: str = "") -> str:
    validated = validate_realtime_session_id(session_id)
    digest = hashlib.sha256(validated.encode("utf-8")).hexdigest()[:16]
    suffix = f"-{context_id[:8]}" if context_id else ""
    return f"jr-interview-{digest}{suffix}"


def participant_identity_for(user_key: str, session_id: str) -> str:
    digest = hashlib.sha256(f"{user_key}:{session_id}".encode("utf-8")).hexdigest()[:20]
    return f"candidate-{digest}"


def issue_livekit_grant(*, session_id: str, user_key: str) -> LiveKitGrant:
    assert_livekit_configured()
    if not user_key.strip():
        raise ValueError("X-Resume-User-Key is required for realtime voice")

    context_id = uuid.uuid4().hex
    room_name = room_name_for_session(session_id, context_id)
    participant_identity = participant_identity_for(user_key, session_id)
    ttl_seconds = max(60, min(config.VOICE_LIVEKIT_TOKEN_TTL_SECONDS, 3600))
    expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
    dispatch_metadata = json.dumps(
        {"context_id": context_id, "schema": "jobradar.voice.v1"},
        ensure_ascii=True,
        separators=(",", ":"),
    )

    token = (
        api.AccessToken(config.LIVEKIT_API_KEY, config.LIVEKIT_API_SECRET)
        .with_identity(participant_identity)
        .with_name("JobRadar candidate")
        .with_ttl(timedelta(seconds=ttl_seconds))
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
                can_publish_sources=["microphone"],
            )
        )
        .with_room_config(
            api.RoomConfiguration(
                empty_timeout=120,
                departure_timeout=30,
                max_participants=2,
                agents=[
                    api.RoomAgentDispatch(
                        agent_name=config.VOICE_LIVEKIT_AGENT_NAME,
                        metadata=dispatch_metadata,
                    )
                ],
            )
        )
        .to_jwt()
    )
    return LiveKitGrant(
        context_id=context_id,
        room_name=room_name,
        participant_identity=participant_identity,
        token=token,
        expires_at=expires_at,
    )
