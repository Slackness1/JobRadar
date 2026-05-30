"""Phase G G2-C — 公司兜底合并进平台栏的去重 + 字段映射测试。"""
import app.services.resume_copilot.platform_aggregator as agg
from app.schemas_resume_copilot import ResumeRecommendationPlatform


def _fake_fallback(monkeypatch, mapping):
    def fake(*, sub_cat, max_companies=5, must_have_only=True):
        return mapping.get(sub_cat, [])
    monkeypatch.setattr(
        "app.services.phase_g.company_fallback.get_fallback_companies", fake
    )


def test_merge_appends_fallback_after_live(monkeypatch):
    _fake_fallback(monkeypatch, {
        "公募权益研究员": [
            {"name": "易方达基金", "tier": "一线公募", "status": "本季暂未开放新增岗位",
             "season": "春招 3-5 月", "verbatim_hint": None, "active_jobs": 0},
        ],
    })
    live = [ResumeRecommendationPlatform(company="招商基金", platform_score=70, n_jobs=3)]
    merged = agg.merge_fallback_companies(live, ["公募权益研究员"])
    assert len(merged) == 2
    assert merged[0].company == "招商基金" and not merged[0].is_fallback
    fb = merged[1]
    assert fb.is_fallback is True
    assert fb.institution_tier == "一线公募"
    assert fb.fallback_status == "本季暂未开放新增岗位"
    assert fb.sub_cat == "公募权益研究员"
    assert fb.hiring_season == "春招 3-5 月"


def test_merge_dedups_against_live_substring(monkeypatch):
    # live "易方达基金管理有限公司" 应吃掉 fallback "易方达基金" (互为子串)
    _fake_fallback(monkeypatch, {
        "公募权益研究员": [
            {"name": "易方达基金", "tier": "一线公募", "status": "", "season": "", "active_jobs": 0},
            {"name": "华夏基金", "tier": "一线公募", "status": "", "season": "", "active_jobs": 0},
        ],
    })
    live = [ResumeRecommendationPlatform(company="易方达基金管理有限公司", platform_score=80, n_jobs=2)]
    merged = agg.merge_fallback_companies(live, ["公募权益研究员"])
    names = [p.company for p in merged]
    assert "易方达基金" not in names  # 被 live 覆盖
    assert "华夏基金" in names


def test_merge_dedups_across_sub_cats(monkeypatch):
    # 同一家公司在两个目标赛道都 must_have, 只补一次
    _fake_fallback(monkeypatch, {
        "公募权益研究员": [{"name": "易方达基金", "tier": "一线公募", "status": "", "season": "", "active_jobs": 0}],
        "行业研究员·消费": [{"name": "易方达基金", "tier": "一线公募", "status": "", "season": "", "active_jobs": 0}],
    })
    merged = agg.merge_fallback_companies([], ["公募权益研究员", "行业研究员·消费"])
    assert len(merged) == 1


def test_merge_does_not_overmerge_distinct_brands(monkeypatch):
    # 招商基金 (live) vs 招商证券 (fallback) 是两家, 不能误并
    _fake_fallback(monkeypatch, {
        "卖方研究员·消费医药周期": [{"name": "招商证券", "tier": "中型券商研究所", "status": "", "season": "", "active_jobs": 0}],
    })
    live = [ResumeRecommendationPlatform(company="招商基金", platform_score=70, n_jobs=1)]
    merged = agg.merge_fallback_companies(live, ["卖方研究员·消费医药周期"])
    assert "招商证券" in [p.company for p in merged]
