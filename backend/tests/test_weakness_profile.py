import json

from app.services.interview.weakness_profile import (
    WeaknessProfile,
    compute_weakness,
)


def _score(overall, hits=None, misses=None, bonuses=None):
    return json.dumps({
        "overall": overall,
        "hits": hits or [],
        "misses": misses or [],
        "bonuses": bonuses or [],
    })


def test_empty_inputs_return_default_profile():
    out = compute_weakness([])
    assert isinstance(out, WeaknessProfile)
    assert out.avg_score is None
    assert out.weak_topics == []
    assert out.strong_topics == []
    assert out.gap_warnings == []


def test_avg_score_ignores_null_score_rows():
    score_jsons = [
        _score(80, hits=["量化"], misses=["STAR"]),
        None,
        _score(60, hits=["技术深度"], misses=["量化"]),
    ]
    out = compute_weakness(score_jsons)
    assert out.avg_score == 70


def test_weak_topics_ranked_by_miss_frequency():
    score_jsons = [
        _score(70, misses=["量化结果", "STAR 结构"]),
        _score(60, misses=["量化结果", "业务理解"]),
        _score(80, misses=["量化结果"]),
    ]
    out = compute_weakness(score_jsons)
    assert out.weak_topics[0] == "量化结果"
    assert "STAR 结构" in out.weak_topics
    assert "业务理解" in out.weak_topics


def test_strong_topics_ranked_by_hit_frequency():
    score_jsons = [
        _score(80, hits=["项目经验", "技术深度"]),
        _score(75, hits=["项目经验", "沟通清晰"]),
    ]
    out = compute_weakness(score_jsons)
    assert out.strong_topics[0] == "项目经验"


def test_gap_warning_when_avg_below_60():
    score_jsons = [_score(40), _score(50)]
    out = compute_weakness(score_jsons)
    assert any("整体分数偏低" in w for w in out.gap_warnings)


def test_handles_malformed_score_json():
    score_jsons = [
        _score(80, hits=["量化"]),
        "not json",
        '{"overall":}',
    ]
    out = compute_weakness(score_jsons)
    assert out.avg_score == 80
