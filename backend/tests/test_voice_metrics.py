import json

from app.services.interview.voice_metrics import (
    VoiceMetrics,
    compute_voice_metrics,
)


def _make_transcript(segments, audio_duration_s):
    """Mock ASR transcript. segments: list of (start_s, end_s, text)."""
    return {
        "audio_duration_s": audio_duration_s,
        "segments": [
            {"start_s": s, "end_s": e, "text": t} for s, e, t in segments
        ],
    }


def test_empty_transcript_returns_all_null_fields():
    out = compute_voice_metrics({})
    assert isinstance(out, VoiceMetrics)
    assert out.filler_rate is None
    assert out.wpm is None
    assert out.pause_count is None


def test_filler_rate_counts_chinese_fillers():
    transcript = _make_transcript(
        [(0.0, 60.0, "嗯 我之前在字节做产品 那个 主要负责 然后呢 就是用户增长")],
        audio_duration_s=60.0,
    )
    out = compute_voice_metrics(transcript)
    # "嗯", "那个", "然后", "就是" = 4 fillers in 60s of audio
    assert out.filler_rate == 4.0  # per minute


def test_wpm_computes_from_char_count_over_duration():
    text = "用户增长是一个长期的工程问题需要持续投入资源做好每一个细节点"  # 30 chars
    transcript = _make_transcript([(0.0, 10.0, text)], audio_duration_s=10.0)
    out = compute_voice_metrics(transcript)
    # 30 chars in 10s = 180 chars/min
    assert out.wpm == 180


def test_pause_count_detects_long_segment_gaps():
    transcript = _make_transcript(
        [
            (0.0, 5.0, "开头一段"),
            (7.0, 10.0, "中间停顿了两秒"),  # 2s gap > 1.5s → 1 pause
            (10.5, 15.0, "继续说"),  # 0.5s gap, not a pause
            (18.0, 20.0, "又停了"),  # 3s gap > 1.5s → 1 pause
        ],
        audio_duration_s=20.0,
    )
    out = compute_voice_metrics(transcript)
    assert out.pause_count == 2


def test_response_latency_is_first_segment_start():
    transcript = _make_transcript(
        [(2.5, 10.0, "答案开头延迟了两秒半")],
        audio_duration_s=10.0,
    )
    out = compute_voice_metrics(transcript)
    assert out.response_latency_ms == 2500


def test_voice_metrics_serializes_to_json():
    out = VoiceMetrics(filler_rate=2.5, wpm=200, pause_count=1, response_latency_ms=800, confidence_score=72)
    serialized = out.to_json()
    parsed = json.loads(serialized)
    assert parsed == {
        "filler_rate": 2.5, "wpm": 200, "pause_count": 1,
        "response_latency_ms": 800, "confidence_score": 72,
    }


def test_zero_duration_does_not_divide_by_zero():
    transcript = _make_transcript([(0.0, 0.0, "嗯")], audio_duration_s=0.0)
    out = compute_voice_metrics(transcript)
    assert out.filler_rate is None
    assert out.wpm is None


# ---------------------------------------------------------------------------
# Task 7: score_confidence_from_transcript tests
# ---------------------------------------------------------------------------

class _StubLLM:
    def __init__(self, raw):
        self._raw = raw

    def chat_text(self, system, user, **_):
        if isinstance(self._raw, Exception):
            raise self._raw
        return self._raw


def test_score_confidence_returns_int_on_clean_response():
    from app.services.interview.voice_metrics import score_confidence_from_transcript
    stub = _StubLLM("75")
    metrics = VoiceMetrics(filler_rate=2.0, wpm=210, pause_count=1, response_latency_ms=600)
    score = score_confidence_from_transcript(_make_transcript([(0, 5, "你好")], 5.0), metrics, llm=stub)
    assert score == 75


def test_score_confidence_strips_extra_whitespace_and_punctuation():
    from app.services.interview.voice_metrics import score_confidence_from_transcript
    stub = _StubLLM("  82.  \n")
    metrics = VoiceMetrics()
    score = score_confidence_from_transcript({}, metrics, llm=stub)
    assert score == 82


def test_score_confidence_returns_none_on_llm_failure():
    from app.services.interview.voice_metrics import score_confidence_from_transcript
    stub = _StubLLM(RuntimeError("down"))
    metrics = VoiceMetrics()
    score = score_confidence_from_transcript({}, metrics, llm=stub)
    assert score is None


def test_score_confidence_returns_none_on_non_numeric_response():
    from app.services.interview.voice_metrics import score_confidence_from_transcript
    stub = _StubLLM("very confident!")
    metrics = VoiceMetrics()
    score = score_confidence_from_transcript({}, metrics, llm=stub)
    assert score is None


def test_score_confidence_clamps_to_0_100_range():
    from app.services.interview.voice_metrics import score_confidence_from_transcript
    stub = _StubLLM("150")
    metrics = VoiceMetrics()
    score = score_confidence_from_transcript({}, metrics, llm=stub)
    assert score == 100
