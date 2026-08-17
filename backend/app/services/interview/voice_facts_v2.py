"""voice-facts-v2 — one definition per metric, one source per metric.

v1 let three different mechanisms (ASR sentence timing, Silero VAD, our own
energy VAD) each produce their own "pause count", and shipped a `wpm` that was
actually characters-per-minute over the whole recording including silence. So a
number in a report could not be traced back to how it was measured.

v2 fixes that by making every metric a self-describing envelope:

    {
      "value": 820,
      "unit": "ms",
      "source": "livekit_vad",
      "definition": "agent_playout_end_to_user_speech_start",
      "version": "voice-facts-v2",
      "quality": "valid",
      "basis": "turn=3"
    }

Rules this module enforces:

  * One metric key has exactly one winning source, chosen by SOURCE_PRIORITY.
    Losing sources are kept under `shadow` for engineering comparison and are
    never part of the student-facing payload.
  * Missing input yields `quality="unavailable"` with `value=None` — never 0,
    and never a substitute measurement pretending to be the real definition.
  * Metrics that only describe the system (latencies, EOT probabilities, pitch)
    are internal. `user_facing()` is the only thing a report may render.
  * No confidence / personality / emotion label exists at any layer.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Iterable, Literal

VERSION = "voice-facts-v2"

Unit = Literal["ms", "s", "cpm", "count", "dbfs", "db", "ratio", "hz", "bool", "text"]
Source = Literal[
    "livekit_vad",          # Silero VAD / turn detector events from the voice agent
    "livekit_session",      # AgentSession state transitions and metrics
    "audio_artifact",       # offline analysis of the consented WAV
    "asr_transcript",       # ASR final text and its sentence timings
    "interview_turn",       # persisted turn row (heard text, interruption flag)
    "legacy_v1",            # historical voice_metrics rows, kept readable
]
Quality = Literal["valid", "degraded", "unavailable", "legacy"]

# Which source wins when several can produce the same metric. First match wins.
SOURCE_PRIORITY: dict[str, tuple[Source, ...]] = {
    "response_start_ms": ("livekit_vad", "audio_artifact"),
    "speech_duration_ms": ("livekit_vad", "audio_artifact", "asr_transcript"),
    "articulation_cpm": ("audio_artifact", "asr_transcript", "legacy_v1"),
    "pause_count": ("audio_artifact", "asr_transcript", "legacy_v1"),
    "pause_total_ms": ("audio_artifact", "asr_transcript"),
    "pause_max_ms": ("audio_artifact", "asr_transcript"),
    "filler_count": ("asr_transcript", "legacy_v1"),
    "input_level_dbfs": ("audio_artifact",),
    "clipping_ratio": ("audio_artifact",),
    "answer_truncated": ("interview_turn",),
}

# Everything a student's report is allowed to show. Anything else is internal.
USER_FACING_KEYS: tuple[str, ...] = (
    "response_start_ms",
    "speech_duration_ms",
    "articulation_cpm",
    "pause_count",
    "pause_total_ms",
    "pause_max_ms",
    "filler_count",
    "input_level_dbfs",
    "clipping_ratio",
    "answer_truncated",
)

# Pause floor for the artifact analyzer's acoustic pauses (matches voice-facts-v1
# acoustic analysis at 500 ms) and for ASR-derived gaps.
ACOUSTIC_PAUSE_FLOOR_MS = 500
ASR_GAP_FLOOR_MS = 1500

# Fillers split by how safely they can be counted in Chinese. Hesitation sounds
# are unambiguous. Discourse markers ("然后", "就是") are ordinary words mid
# sentence, so they only count when they open a sentence — otherwise a fluent
# answer gets punished for using connectives.
FILLERS_HESITATION: tuple[str, ...] = ("嗯", "呃", "唔", "额", "啊", "哦")
FILLERS_DISCOURSE: tuple[str, ...] = ("那个", "然后", "就是", "这个", "对吧", "怎么说")

_HESITATION_RE = re.compile("|".join(re.escape(word) for word in FILLERS_HESITATION))
_DISCOURSE_RE = re.compile("|".join(re.escape(word) for word in FILLERS_DISCOURSE))
_SENTENCE_SPLIT_RE = re.compile(r"[。！？!?；;，,、\n]")


def metric(
    value: Any,
    *,
    unit: Unit,
    source: Source,
    definition: str,
    quality: Quality = "valid",
    basis: str | None = None,
) -> dict[str, Any]:
    """Build one self-describing metric envelope."""
    payload: dict[str, Any] = {
        "value": value,
        "unit": unit,
        "source": source,
        "definition": definition,
        "version": VERSION,
        "quality": "unavailable" if value is None and quality != "legacy" else quality,
    }
    if basis:
        payload["basis"] = basis
    return payload


def unavailable(
    *, unit: Unit, source: Source, definition: str, basis: str | None = None
) -> dict[str, Any]:
    return metric(
        None, unit=unit, source=source, definition=definition,
        quality="unavailable", basis=basis,
    )


# ── filler detection ────────────────────────────────────────────────────────


def detect_fillers(segments: Iterable[dict]) -> tuple[int, list[dict], Quality]:
    """Count fillers and report where they are.

    Returns (count, positions, quality). `quality` is "degraded" when the only
    hits are discourse markers, because those are judgement calls rather than
    measurements — the report should not present them as hard facts.
    """
    positions: list[dict] = []
    hesitation_hits = 0
    for index, segment in enumerate(segments):
        text = str(segment.get("text") or "")
        if not text:
            continue
        for found in _HESITATION_RE.finditer(text):
            hesitation_hits += 1
            positions.append({
                "segment_index": index,
                "char_offset": found.start(),
                "token": found.group(0),
                "kind": "hesitation",
                "start_s": segment.get("start_s"),
            })
        # Sentence-initial discourse markers only.
        offset = 0
        for sentence in _SENTENCE_SPLIT_RE.split(text):
            stripped = sentence.lstrip()
            lead = len(sentence) - len(stripped)
            match = _DISCOURSE_RE.match(stripped)
            if match:
                positions.append({
                    "segment_index": index,
                    "char_offset": offset + lead,
                    "token": match.group(0),
                    "kind": "discourse",
                    "start_s": segment.get("start_s"),
                })
            offset += len(sentence) + 1
    positions.sort(key=lambda item: (item["segment_index"], item["char_offset"]))
    quality: Quality = "valid" if hesitation_hits or not positions else "degraded"
    return len(positions), positions, quality


# ── per-source builders ─────────────────────────────────────────────────────


def from_asr_transcript(asr: dict | None) -> dict[str, dict]:
    """Metrics the ASR final transcript can support on its own.

    ASR sentence timing is provider-side and coarse, so anything timing-derived
    here is `degraded`: it is a fallback for turns with no consented audio, not
    an acoustic measurement.
    """
    if not asr or not isinstance(asr, dict):
        return {}
    segments = [s for s in (asr.get("segments") or []) if isinstance(s, dict)]
    out: dict[str, dict] = {}

    timed = [
        s for s in segments
        if isinstance(s.get("start_s"), (int, float)) and isinstance(s.get("end_s"), (int, float))
    ]
    characters = sum(len(re.findall(r"[\w一-鿿]", str(s.get("text") or ""))) for s in segments)

    if timed:
        voiced_s = sum(float(s["end_s"]) - float(s["start_s"]) for s in timed)
        if voiced_s > 0:
            out["speech_duration_ms"] = metric(
                round(voiced_s * 1000), unit="ms", source="asr_transcript",
                definition="sum_of_asr_sentence_spans", quality="degraded",
            )
            out["articulation_cpm"] = metric(
                round(characters / (voiced_s / 60)), unit="cpm", source="asr_transcript",
                definition="characters_per_minute_of_asr_sentence_time", quality="degraded",
            )
        gaps = [
            round((float(b["start_s"]) - float(a["end_s"])) * 1000)
            for a, b in zip(timed, timed[1:])
            if float(b["start_s"]) - float(a["end_s"]) > 0
        ]
        long_gaps = [gap for gap in gaps if gap >= ASR_GAP_FLOOR_MS]
        out["pause_count"] = metric(
            len(long_gaps), unit="count", source="asr_transcript",
            definition=f"asr_sentence_gaps_over_{ASR_GAP_FLOOR_MS}ms", quality="degraded",
        )
        if long_gaps:
            out["pause_total_ms"] = metric(
                sum(long_gaps), unit="ms", source="asr_transcript",
                definition=f"asr_sentence_gaps_over_{ASR_GAP_FLOOR_MS}ms", quality="degraded",
            )
            out["pause_max_ms"] = metric(
                max(long_gaps), unit="ms", source="asr_transcript",
                definition="longest_asr_sentence_gap", quality="degraded",
            )

    count, positions, quality = detect_fillers(segments)
    out["filler_count"] = metric(
        count, unit="count", source="asr_transcript",
        definition="hesitation_sounds_plus_sentence_initial_discourse_markers",
        quality=quality,
    )
    out["_filler_positions"] = {"value": positions, "source": "asr_transcript", "version": VERSION}
    return out


def from_audio_artifact(features: dict | None, flags: Iterable[str] | None = None) -> dict[str, dict]:
    """Metrics from the consented WAV — the acoustic source of truth."""
    if not features or not isinstance(features, dict):
        return {}
    flag_set = set(flags or [])
    speech = features.get("speech") or {}
    pauses = features.get("pauses") or {}
    delivery = features.get("delivery") or {}
    energy = features.get("energy") or {}
    pitch = features.get("pitch") or {}
    low_signal = "insufficient_speech" in flag_set or "low_input_level" in flag_set
    base_quality: Quality = "degraded" if low_signal else "valid"
    out: dict[str, dict] = {}

    first_speech = speech.get("first_speech_ms")
    out["response_start_ms"] = metric(
        first_speech, unit="ms", source="audio_artifact",
        # Not the same clock as the LiveKit definition: the recording starts when
        # the student's turn starts, so this omits any TTS tail. Kept explicit.
        definition="recording_start_to_first_voiced_frame",
        quality="degraded" if first_speech is not None else "unavailable",
    )
    speech_s = speech.get("speech_duration_seconds")
    out["speech_duration_ms"] = metric(
        round(speech_s * 1000) if isinstance(speech_s, (int, float)) else None,
        unit="ms", source="audio_artifact",
        definition="voiced_frames_total", quality=base_quality,
    )
    out["articulation_cpm"] = metric(
        delivery.get("articulation_cpm"), unit="cpm", source="audio_artifact",
        definition="transcript_characters_per_minute_of_voiced_time", quality=base_quality,
    )
    out["pause_count"] = metric(
        pauses.get("count"), unit="count", source="audio_artifact",
        definition=f"acoustic_gaps_over_{ACOUSTIC_PAUSE_FLOOR_MS}ms_between_voiced_segments",
        quality=base_quality,
    )
    total_s = pauses.get("total_seconds")
    out["pause_total_ms"] = metric(
        round(total_s * 1000) if isinstance(total_s, (int, float)) else None,
        unit="ms", source="audio_artifact",
        definition=f"acoustic_gaps_over_{ACOUSTIC_PAUSE_FLOOR_MS}ms_total", quality=base_quality,
    )
    max_s = pauses.get("max_seconds")
    out["pause_max_ms"] = metric(
        round(max_s * 1000) if isinstance(max_s, (int, float)) else None,
        unit="ms", source="audio_artifact",
        definition="longest_acoustic_gap", quality=base_quality,
    )
    out["input_level_dbfs"] = metric(
        energy.get("mean_dbfs"), unit="dbfs", source="audio_artifact",
        definition="mean_dbfs_over_voiced_frames", quality=base_quality,
    )
    out["clipping_ratio"] = metric(
        energy.get("clipping_ratio"), unit="ratio", source="audio_artifact",
        definition="fraction_of_samples_at_full_scale",
    )
    # Internal-only: dynamic range and pitch describe the recording, and pitch in
    # particular has no validated interpretation. Kept out of USER_FACING_KEYS.
    out["dynamic_range_db"] = metric(
        energy.get("dynamic_range_db"), unit="db", source="audio_artifact",
        definition="p90_minus_p10_dbfs",
    )
    for key, unit in (("median_hz", "hz"), ("p10_hz", "hz"), ("p90_hz", "hz")):
        out[f"pitch_{key}"] = metric(
            pitch.get(key), unit=unit, source="audio_artifact",
            definition=f"autocorrelation_f0_{key}",
            quality="degraded" if "pitch_unavailable" in flag_set else "valid",
        )
    return out


def from_interview_turn(turn: Any) -> dict[str, dict]:
    """Facts the turn row itself owns (what the student actually heard)."""
    if turn is None:
        return {}
    interrupted = bool(getattr(turn, "question_interrupted", False))
    return {
        "answer_truncated": metric(
            interrupted, unit="bool", source="interview_turn",
            definition="question_playback_was_interrupted_by_user",
        ),
        "_heard_question": {
            "value": str(getattr(turn, "question_heard_text", "") or ""),
            "source": "interview_turn",
            "version": VERSION,
        },
    }


def from_legacy_v1(voice_metrics: dict | str | None) -> dict[str, dict]:
    """Read historical v1 rows without pretending they are v2 measurements.

    `wpm` was characters-per-minute over the whole recording (silence included),
    so it becomes `articulation_cpm` with quality="legacy" and a definition that
    says exactly that. `confidence_score` is dropped, never surfaced.
    """
    if isinstance(voice_metrics, str):
        try:
            voice_metrics = json.loads(voice_metrics)
        except (TypeError, ValueError):
            return {}
    if not voice_metrics or not isinstance(voice_metrics, dict):
        return {}
    out: dict[str, dict] = {}
    if voice_metrics.get("wpm") is not None:
        out["articulation_cpm"] = metric(
            voice_metrics["wpm"], unit="cpm", source="legacy_v1",
            definition="v1_characters_per_minute_over_total_recording_including_silence",
            quality="legacy",
        )
    if voice_metrics.get("pause_count") is not None:
        out["pause_count"] = metric(
            voice_metrics["pause_count"], unit="count", source="legacy_v1",
            definition=f"v1_asr_sentence_gaps_over_{ASR_GAP_FLOOR_MS}ms", quality="legacy",
        )
    if voice_metrics.get("filler_rate") is not None:
        out["filler_count"] = metric(
            None, unit="count", source="legacy_v1",
            definition="v1_stored_only_a_per_minute_rate_not_a_count",
            quality="unavailable",
        )
    # v1 response_latency_ms measured nothing we can defend (it was often the
    # default 0) and confidence_score is permanently retired — both dropped.
    return out


# ── realtime (LiveKit) interaction metrics ──────────────────────────────────

_REALTIME_DEFINITIONS: dict[str, tuple[Unit, str]] = {
    "stt_final_latency_ms": ("ms", "asr_final_arrival_minus_user_speech_end"),
    "eou_decision_latency_ms": ("ms", "turn_committed_minus_user_speech_end"),
    "agent_response_latency_ms": ("ms", "first_agent_audio_minus_turn_committed"),
    "barge_in_stop_latency_ms": ("ms", "agent_audio_stopped_minus_valid_interruption_start"),
    "response_start_latency_ms": ("ms", "user_speech_start_minus_agent_playout_end"),
    "overlap_duration_ms": ("ms", "user_and_agent_speaking_simultaneously"),
    "eot_probability": ("ratio", "turn_detector_end_of_turn_probability"),
    "eot_threshold": ("ratio", "turn_detector_commit_threshold"),
    "endpoint_delay_mode": ("text", "min_delay_or_max_delay_used_for_commit"),
    "false_interruption_recovered": ("bool", "interruption_was_rejected_and_playback_resumed"),
}


def _event_time(event: Any) -> datetime | None:
    """Prefer the emit-time stamp; DB insert time is polluted by queueing."""
    return getattr(event, "occurred_at", None) or getattr(event, "created_at", None)


def _payload(event: Any) -> dict:
    try:
        loaded = json.loads(getattr(event, "payload_json", "") or "{}")
    except (TypeError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def from_realtime_events(events: Iterable[Any], *, basis: str | None = None) -> dict[str, dict]:
    """Interaction latencies for one turn's slice of the realtime event stream.

    Every metric starts as `unavailable`; a value only appears when both anchors
    of its definition are present. A missing LiveKit deployment therefore yields
    an honest wall of `unavailable` rather than zeros.
    """
    out = {
        key: unavailable(unit=unit, source="livekit_session", definition=definition, basis=basis)
        for key, (unit, definition) in _REALTIME_DEFINITIONS.items()
    }
    ordered = [e for e in events if _event_time(e) is not None]
    ordered.sort(key=lambda e: _event_time(e))
    if not ordered:
        return out

    user_speech_end: datetime | None = None
    agent_playout_end: datetime | None = None
    user_speech_start: datetime | None = None
    turn_committed: datetime | None = None
    interruption_start: datetime | None = None

    def set_metric(key: str, value: Any, *, source: Source = "livekit_session") -> None:
        unit, definition = _REALTIME_DEFINITIONS[key]
        out[key] = metric(value, unit=unit, source=source, definition=definition, basis=basis)

    for event in ordered:
        kind = str(getattr(event, "event_type", ""))
        payload = _payload(event)
        stamp = _event_time(event)

        if kind == "user_state":
            if payload.get("new") == "speaking":
                user_speech_start = stamp
                if agent_playout_end and stamp >= agent_playout_end:
                    set_metric(
                        "response_start_latency_ms",
                        int((stamp - agent_playout_end).total_seconds() * 1000),
                        source="livekit_vad",
                    )
            elif payload.get("old") == "speaking":
                user_speech_end = stamp
        elif kind == "agent_state":
            if payload.get("new") == "speaking":
                if turn_committed and stamp >= turn_committed:
                    set_metric(
                        "agent_response_latency_ms",
                        int((stamp - turn_committed).total_seconds() * 1000),
                    )
            elif payload.get("old") == "speaking":
                agent_playout_end = stamp
                if interruption_start and stamp >= interruption_start:
                    set_metric(
                        "barge_in_stop_latency_ms",
                        int((stamp - interruption_start).total_seconds() * 1000),
                    )
                    interruption_start = None
        elif kind == "conversation_item" and payload.get("role") == "user":
            if user_speech_end and stamp >= user_speech_end:
                set_metric(
                    "stt_final_latency_ms",
                    int((stamp - user_speech_end).total_seconds() * 1000),
                )
            turn_committed = turn_committed or stamp
            if user_speech_end and stamp >= user_speech_end:
                set_metric(
                    "eou_decision_latency_ms",
                    int((stamp - user_speech_end).total_seconds() * 1000),
                )
        elif kind == "manual_turn_committed":
            turn_committed = stamp
            if user_speech_end and stamp >= user_speech_end:
                set_metric(
                    "eou_decision_latency_ms",
                    int((stamp - user_speech_end).total_seconds() * 1000),
                )
            set_metric("endpoint_delay_mode", "manual_commit")
        elif kind == "eot_prediction":
            if payload.get("probability") is not None:
                set_metric("eot_probability", payload.get("probability"), source="livekit_vad")
            if payload.get("threshold") is not None:
                set_metric("eot_threshold", payload.get("threshold"), source="livekit_vad")
            delay = payload.get("delay")
            if delay is not None:
                set_metric("endpoint_delay_mode", f"delay={delay}")
        elif kind == "overlapping_speech":
            total = payload.get("total_duration")
            if total is not None:
                set_metric("overlap_duration_ms", int(float(total) * 1000), source="livekit_vad")
            if payload.get("is_interruption"):
                detection_delay = float(payload.get("detection_delay") or 0.0)
                interruption_start = stamp
                if detection_delay:
                    from datetime import timedelta

                    interruption_start = stamp - timedelta(seconds=detection_delay)
        elif kind in {"explicit_interruption"}:
            interruption_start = stamp
        elif kind == "false_interruption":
            set_metric("false_interruption_recovered", bool(payload.get("resumed")))

    # user_speech_start is used for the strict response-start definition above;
    # keeping the reference silences "unused" readings of the flow.
    del user_speech_start
    return out


# ── resolution ──────────────────────────────────────────────────────────────


def resolve(*sources: dict[str, dict]) -> tuple[dict[str, dict], dict[str, list[dict]]]:
    """Pick one winning metric per key by SOURCE_PRIORITY; keep the rest as shadow."""
    candidates: dict[str, list[dict]] = {}
    passthrough: dict[str, dict] = {}
    for bundle in sources:
        for key, value in (bundle or {}).items():
            if key.startswith("_"):
                passthrough[key] = value
                continue
            candidates.setdefault(key, []).append(value)

    winners: dict[str, dict] = {}
    shadow: dict[str, list[dict]] = {}
    for key, options in candidates.items():
        priority = SOURCE_PRIORITY.get(key)
        if priority:
            usable = [
                option for option in options
                if option.get("quality") != "unavailable" or option.get("value") is not None
            ]
            pool = usable or options
            ranked = sorted(
                pool,
                key=lambda option: priority.index(option["source"])
                if option.get("source") in priority else len(priority),
            )
        else:
            ranked = options
        winners[key] = ranked[0]
        if len(ranked) > 1:
            shadow[key] = ranked[1:]
    winners.update(passthrough)
    return winners, shadow


def build_turn_facts(
    *,
    turn: Any = None,
    asr_transcript: dict | None = None,
    artifact_features: dict | None = None,
    artifact_flags: Iterable[str] | None = None,
    realtime_events: Iterable[Any] | None = None,
    legacy_voice_metrics: dict | str | None = None,
) -> dict[str, Any]:
    """Assemble all facts for one turn, with provenance and shadow values."""
    metrics, shadow = resolve(
        from_realtime_events(realtime_events or [], basis=_turn_basis(turn)),
        from_audio_artifact(artifact_features, artifact_flags),
        from_asr_transcript(asr_transcript),
        from_interview_turn(turn),
        from_legacy_v1(legacy_voice_metrics),
    )
    return {"version": VERSION, "metrics": metrics, "shadow": shadow}


def _turn_basis(turn: Any) -> str | None:
    index = getattr(turn, "turn_index", None)
    return f"turn={index}" if index is not None else None


def user_facing(facts: dict[str, Any]) -> dict[str, Any]:
    """The only projection a student-facing report may render."""
    metrics = (facts or {}).get("metrics") or {}
    shown = {key: metrics[key] for key in USER_FACING_KEYS if key in metrics}
    positions = (metrics.get("_filler_positions") or {}).get("value") or []
    return {
        "version": VERSION,
        "metrics": shown,
        "filler_positions": positions,
        # Deliberately absent: every latency, EOT probability, pitch, dynamic
        # range and shadow value. Those exist to tune the system, not to judge
        # the candidate.
    }
