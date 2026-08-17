"""voice-facts-v2: one definition per metric, one source per metric.

These tests pin the contract that makes the numbers defensible: provenance on
every value, a single winning source per key, `unavailable` instead of a
substitute measurement, internal-only values kept out of the student payload,
and no confidence/personality label anywhere.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from types import SimpleNamespace

from app.services.interview import voice_facts_v2 as v2


def _artifact_features(**overrides):
    features = {
        "version": "voice-facts-v1",
        "duration_seconds": 30.0,
        "speech": {
            "first_speech_ms": 820,
            "speech_duration_seconds": 24.5,
            "voiced_ratio": 0.81,
            "segment_count": 4,
            "segments": [],
        },
        "pauses": {"count": 3, "total_seconds": 2.8, "mean_seconds": 0.93, "max_seconds": 1.4},
        "delivery": {"articulation_cpm": 268},
        "energy": {"mean_dbfs": -22.4, "dynamic_range_db": 18.2, "clipping_ratio": 0.0},
        "pitch": {"sample_count": 220, "median_hz": 178.0, "p10_hz": 150.0, "p90_hz": 214.0},
    }
    features.update(overrides)
    return features


def _asr(*segments):
    return {
        "audio_duration_s": 30.0,
        "segments": [
            {"start_s": start, "end_s": end, "text": text} for start, end, text in segments
        ],
    }


def _event(event_type, seconds, payload=None, turn_index=0):
    base = datetime(2026, 8, 17, 10, 0, 0)
    return SimpleNamespace(
        event_type=event_type,
        turn_index=turn_index,
        payload_json=json.dumps(payload or {}),
        occurred_at=base + timedelta(seconds=seconds),
        created_at=base + timedelta(seconds=seconds + 5),  # polluted insert time
    )


# ── envelope ────────────────────────────────────────────────────────────────


def test_every_metric_carries_provenance_and_definition():
    facts = v2.build_turn_facts(artifact_features=_artifact_features())
    pause = facts["metrics"]["pause_count"]
    assert pause["value"] == 3
    assert pause["unit"] == "count"
    assert pause["source"] == "audio_artifact"
    assert pause["definition"] == "acoustic_gaps_over_500ms_between_voiced_segments"
    assert pause["version"] == "voice-facts-v2"
    assert pause["quality"] == "valid"


def test_missing_input_is_unavailable_not_zero():
    facts = v2.build_turn_facts()
    realtime = facts["metrics"]["stt_final_latency_ms"]
    assert realtime["value"] is None
    assert realtime["quality"] == "unavailable"
    # No metric may silently substitute 0 for "we could not measure this".
    assert all(
        item["value"] is not None or item["quality"] in {"unavailable", "legacy"}
        for item in facts["metrics"].values()
        if isinstance(item, dict) and "quality" in item
    )


def test_low_signal_recording_downgrades_quality():
    facts = v2.build_turn_facts(
        artifact_features=_artifact_features(),
        artifact_flags=["insufficient_speech", "low_input_level"],
    )
    assert facts["metrics"]["speech_duration_ms"]["quality"] == "degraded"
    assert facts["metrics"]["articulation_cpm"]["quality"] == "degraded"


# ── single source of truth ──────────────────────────────────────────────────


def test_acoustic_pauses_beat_asr_pauses_and_the_loser_is_kept_as_shadow():
    facts = v2.build_turn_facts(
        artifact_features=_artifact_features(),
        asr_transcript=_asr((0.5, 8.0, "第一段"), (11.0, 20.0, "第二段")),
    )
    winner = facts["metrics"]["pause_count"]
    assert winner["source"] == "audio_artifact"
    shadow_sources = [item["source"] for item in facts["shadow"]["pause_count"]]
    assert "asr_transcript" in shadow_sources
    # The student payload must never show two different pause counts.
    shown = v2.user_facing(facts)
    assert "shadow" not in shown
    assert shown["metrics"]["pause_count"]["source"] == "audio_artifact"


def test_asr_only_turn_falls_back_and_says_it_is_degraded():
    facts = v2.build_turn_facts(asr_transcript=_asr((0.5, 8.0, "我负责估值建模"), (11.0, 20.0, "然后复盘")))
    pause = facts["metrics"]["pause_count"]
    assert pause["source"] == "asr_transcript"
    assert pause["quality"] == "degraded"
    assert pause["definition"] == "asr_sentence_gaps_over_1500ms"


def test_legacy_wpm_becomes_cpm_with_an_honest_definition():
    facts = v2.build_turn_facts(
        legacy_voice_metrics=json.dumps({
            "wpm": 240, "pause_count": 2, "filler_rate": 3.5,
            "response_latency_ms": 0, "confidence_score": 72,
        })
    )
    cpm = facts["metrics"]["articulation_cpm"]
    assert cpm["value"] == 240
    assert cpm["quality"] == "legacy"
    assert "including_silence" in cpm["definition"]
    # A rate cannot be read back as a count.
    assert facts["metrics"]["filler_count"]["quality"] == "unavailable"
    # v1's always-zero latency and the retired confidence label are gone.
    assert "response_latency_ms" not in facts["metrics"]
    assert "confidence" not in json.dumps(facts).lower()


def test_fresh_artifact_outranks_legacy_v1():
    facts = v2.build_turn_facts(
        artifact_features=_artifact_features(),
        legacy_voice_metrics={"wpm": 240, "pause_count": 9},
    )
    assert facts["metrics"]["articulation_cpm"]["source"] == "audio_artifact"
    assert facts["metrics"]["pause_count"]["value"] == 3


# ── fillers ─────────────────────────────────────────────────────────────────


def test_hesitation_sounds_are_counted_with_positions():
    count, positions, quality = v2.detect_fillers([
        {"start_s": 0.2, "end_s": 6.0, "text": "嗯，我负责估值建模，呃，主要是 DCF"},
    ])
    assert count == 2
    assert quality == "valid"
    assert [item["token"] for item in positions] == ["嗯", "呃"]
    assert positions[0]["char_offset"] == 0
    assert positions[0]["segment_index"] == 0


def test_mid_sentence_connectives_are_not_punished_as_fillers():
    """"然后" as a connective is ordinary Chinese; only sentence-initial counts."""
    count, positions, _ = v2.detect_fillers([
        {"start_s": 0, "end_s": 5, "text": "我先做了尽调然后完成了估值模型"},
    ])
    assert count == 0
    assert positions == []

    count, positions, quality = v2.detect_fillers([
        {"start_s": 0, "end_s": 5, "text": "然后我完成了估值模型"},
    ])
    assert count == 1
    assert positions[0]["kind"] == "discourse"
    # Discourse-only hits are a judgement call, so the metric says so.
    assert quality == "degraded"


def test_filler_positions_are_not_a_metric_but_travel_with_the_payload():
    facts = v2.build_turn_facts(asr_transcript=_asr((0.2, 6.0, "嗯，我负责估值建模")))
    shown = v2.user_facing(facts)
    assert shown["metrics"]["filler_count"]["value"] == 1
    assert shown["filler_positions"][0]["token"] == "嗯"


# ── realtime interaction metrics ────────────────────────────────────────────


def test_latencies_use_emit_time_not_db_insert_time():
    """created_at includes our own queueing; occurred_at is the real clock."""
    events = [
        _event("user_state", 10.0, {"old": "speaking", "new": "listening"}),
        _event("conversation_item", 10.4, {"role": "user", "text": "我负责估值建模"}),
        _event("agent_state", 11.1, {"old": "listening", "new": "speaking"}),
    ]
    metrics = v2.from_realtime_events(events, basis="turn=0")
    assert metrics["stt_final_latency_ms"]["value"] == 400
    assert metrics["eou_decision_latency_ms"]["value"] == 400
    assert metrics["agent_response_latency_ms"]["value"] == 700
    assert metrics["stt_final_latency_ms"]["basis"] == "turn=0"


def test_barge_in_stop_latency_backs_out_the_detection_delay():
    events = [
        _event("agent_state", 5.0, {"old": "listening", "new": "speaking"}),
        _event("overlapping_speech", 6.5, {
            "is_interruption": True, "total_duration": 0.9, "detection_delay": 0.2,
        }),
        _event("agent_state", 6.75, {"old": "speaking", "new": "listening"}),
    ]
    metrics = v2.from_realtime_events(events)
    # interruption really started at 6.3s (6.5 - 0.2), playback stopped at 6.75s
    assert metrics["barge_in_stop_latency_ms"]["value"] == 450
    assert metrics["overlap_duration_ms"]["value"] == 900


def test_response_start_latency_measures_from_playout_end():
    events = [
        _event("agent_state", 4.0, {"old": "speaking", "new": "listening"}),
        _event("user_state", 5.6, {"old": "listening", "new": "speaking"}),
    ]
    metrics = v2.from_realtime_events(events)
    assert metrics["response_start_latency_ms"]["value"] == 1600
    assert metrics["response_start_latency_ms"]["source"] == "livekit_vad"


def test_endpoint_decision_and_false_interruption_are_recorded():
    events = [
        _event("eot_prediction", 9.0, {"probability": 0.86, "threshold": 0.7, "delay": 0.6}),
        _event("false_interruption", 9.4, {"resumed": True}),
    ]
    metrics = v2.from_realtime_events(events)
    assert metrics["eot_probability"]["value"] == 0.86
    assert metrics["eot_threshold"]["value"] == 0.7
    assert metrics["endpoint_delay_mode"]["value"] == "delay=0.6"
    assert metrics["false_interruption_recovered"]["value"] is True


def test_manual_commit_is_labelled_as_such():
    events = [
        _event("user_state", 8.0, {"old": "speaking", "new": "listening"}),
        _event("manual_turn_committed", 8.9, {"characters": 120}),
    ]
    metrics = v2.from_realtime_events(events)
    assert metrics["eou_decision_latency_ms"]["value"] == 900
    assert metrics["endpoint_delay_mode"]["value"] == "manual_commit"


# ── what a student may see ──────────────────────────────────────────────────


def test_student_payload_hides_system_tuning_metrics():
    facts = v2.build_turn_facts(
        artifact_features=_artifact_features(),
        realtime_events=[
            _event("user_state", 10.0, {"old": "speaking", "new": "listening"}),
            _event("conversation_item", 10.4, {"role": "user", "text": "答案"}),
        ],
    )
    shown = v2.user_facing(facts)
    hidden = {
        "stt_final_latency_ms", "eou_decision_latency_ms", "agent_response_latency_ms",
        "barge_in_stop_latency_ms", "response_start_latency_ms", "overlap_duration_ms",
        "eot_probability", "eot_threshold", "endpoint_delay_mode",
        "false_interruption_recovered", "dynamic_range_db",
        "pitch_median_hz", "pitch_p10_hz", "pitch_p90_hz",
    }
    assert hidden.isdisjoint(shown["metrics"].keys())
    assert set(shown["metrics"]).issubset(set(v2.USER_FACING_KEYS))


def test_pitch_never_reaches_a_student_payload():
    facts = v2.build_turn_facts(artifact_features=_artifact_features())
    assert facts["metrics"]["pitch_median_hz"]["value"] == 178.0  # internal use is fine
    assert "pitch" not in json.dumps(v2.user_facing(facts))


def test_no_confidence_or_personality_label_exists_anywhere():
    facts = v2.build_turn_facts(
        artifact_features=_artifact_features(),
        asr_transcript=_asr((0.2, 6.0, "嗯，我负责估值建模")),
        legacy_voice_metrics={"wpm": 240, "confidence_score": 88},
        realtime_events=[_event("eot_prediction", 3.0, {"probability": 0.9})],
    )
    blob = json.dumps(facts, ensure_ascii=False)
    for banned in ("confidence_score", "自信", "性格", "personality", "emotion"):
        assert banned not in blob


def test_answer_truncated_comes_from_the_turn_row():
    turn = SimpleNamespace(
        turn_index=2, question_interrupted=True, question_heard_text="请讲一个你主导的",
    )
    facts = v2.build_turn_facts(turn=turn, artifact_features=_artifact_features())
    truncated = facts["metrics"]["answer_truncated"]
    assert truncated["value"] is True
    assert truncated["source"] == "interview_turn"
    assert v2.user_facing(facts)["metrics"]["answer_truncated"]["value"] is True
