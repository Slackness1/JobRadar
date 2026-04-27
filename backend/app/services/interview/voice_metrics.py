"""Compute voice-quality metrics from an ASR transcript.

Pure-python (no LLM) for the deterministic features. Confidence scoring
needs an LLM and lives in a separate function so failures of the LLM
sub-call don't take down the deterministic stats.

ASR transcript shape:

    {
      "audio_duration_s": float,
      "segments": [
        {"start_s": float, "end_s": float, "text": str},
        ...
      ]
    }

All fields can be None on the returned VoiceMetrics — represents
"could not compute" (insufficient signal, division-by-zero, etc), not zero.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from typing import Protocol


_FILLER_WORDS = ("嗯", "啊", "那个", "然后", "就是", "对", "呢", "诶")
_PAUSE_THRESHOLD_S = 1.5

# Pre-compiled pattern: match each filler only at the start of a token
# (after a space or at the beginning of the string) so that, e.g., "呢"
# in "然后呢" is not double-counted alongside "然后".
_FILLER_RE = re.compile(
    r"(?:(?<=\s)|^)(?:" + "|".join(re.escape(f) for f in _FILLER_WORDS) + ")",
    re.MULTILINE,
)


@dataclass(slots=True)
class VoiceMetrics:
    filler_rate: float | None = None
    wpm: int | None = None
    pause_count: int | None = None
    response_latency_ms: int | None = None
    confidence_score: int | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


def _count_fillers(text: str) -> int:
    """Count filler words that start a token (after space or at string start).

    Matching only at token boundaries prevents double-counting: e.g. "呢" in
    "然后呢" is not counted because it is not at the start of a token.
    """
    return len(_FILLER_RE.findall(text))


def compute_voice_metrics(transcript: dict) -> VoiceMetrics:
    """Compute deterministic voice metrics from an ASR transcript dict.

    Returns a VoiceMetrics with all fields possibly None (meaning: not enough
    signal). Never raises — bad input → fields are None.
    """
    if not isinstance(transcript, dict):
        return VoiceMetrics()

    segments = transcript.get("segments") or []
    duration_s = float(transcript.get("audio_duration_s") or 0.0)

    if not segments:
        return VoiceMetrics()

    full_text = "".join(str(seg.get("text") or "") for seg in segments)
    char_count = len(re.sub(r"\s+", "", full_text))

    metrics = VoiceMetrics()

    if duration_s > 0:
        fillers = _count_fillers(full_text)
        metrics.filler_rate = round(fillers * 60.0 / duration_s, 2)
        metrics.wpm = int(round(char_count * 60.0 / duration_s))

    pauses = 0
    for prev, curr in zip(segments, segments[1:]):
        prev_end = float(prev.get("end_s") or 0.0)
        curr_start = float(curr.get("start_s") or 0.0)
        if curr_start - prev_end > _PAUSE_THRESHOLD_S:
            pauses += 1
    metrics.pause_count = pauses

    first_start = float(segments[0].get("start_s") or 0.0)
    metrics.response_latency_ms = int(round(first_start * 1000))

    return metrics


class _LLMClient(Protocol):
    def chat_text(self, system: str, user: str, **kwargs) -> object: ...


def score_confidence_from_transcript(
    transcript: dict,
    metrics: VoiceMetrics,
    llm: _LLMClient,
) -> int | None:
    """Ask the LLM to rate confidence 0-100 from transcript + cadence features.

    Returns None on any failure (network, non-numeric response, etc).
    """
    from app.services.interview.prompts import CONFIDENCE_SYSTEM

    payload = json.dumps({
        "transcript": transcript,
        "cadence": {
            "filler_rate": metrics.filler_rate,
            "wpm": metrics.wpm,
            "pause_count": metrics.pause_count,
            "response_latency_ms": metrics.response_latency_ms,
        },
    }, ensure_ascii=False)

    try:
        raw = llm.chat_text(system=CONFIDENCE_SYSTEM, user=payload)
    except Exception:
        return None

    if not isinstance(raw, str):
        return None

    match = re.search(r"\d+", raw)
    if not match:
        return None

    try:
        n = int(match.group())
    except ValueError:
        return None

    return max(0, min(100, n))
