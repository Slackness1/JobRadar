"""互联网重点公司分档名单 — 子串匹配 + 推荐桶内档次先验 + 噪声不命中。"""
from __future__ import annotations

from types import SimpleNamespace

from app.services.phase_g.tier_fit.internet_tiers import internet_tier_of
from app.services.resume_copilot.recommend_search import (
    _curated_internet_boost,
    apply_quality_priors,
)


def test_top_names_match_tier1_even_with_subsidiary_prefix():
    # 口径 2026-06-12: T1 = 字节系/腾讯系/阿里系+蚂蚁/美团/小红书(默认优先投)。
    # 库里真名带地区/子公司前缀 — 子串匹配必须命中(精确集合会漏)
    assert internet_tier_of("深圳市腾讯计算机系统有限公司") == "tier1"
    assert internet_tier_of("字节/抖音") == "tier1"
    assert internet_tier_of("蚂蚁科技集团股份有限公司") == "tier1"
    assert internet_tier_of("行吟信息科技(上海)有限公司") == "tier1"


def test_second_tier_names_match_tier2():
    # 口径 2026-06-12: 百度/京东/拼多多/快手/滴滴/携程/网易/B站/小米 在 T2(看业务线)
    assert internet_tier_of("百度在线网络技术（北京）有限公司") == "tier2"
    assert internet_tier_of("昆仑芯") == "tier2"
    assert internet_tier_of("携程") == "tier2"
    assert internet_tier_of("蔚来") == "tier2"
    assert internet_tier_of("上海米哈游网络科技股份有限公司") == "tier2"


def test_ai_native_companies_are_special_tier_not_t1_t2():
    # AI 原生公司单列档(高潜高风险), 不混入 T1/T2 —— 口径 2026-06-12
    assert internet_tier_of("北京月之暗面科技有限公司") == "ai_special"
    assert internet_tier_of("深度求索") == "ai_special"
    assert internet_tier_of("智谱AI") == "ai_special"
    assert internet_tier_of("MiniMax") == "ai_special"


def test_mislabeled_noise_does_not_match():
    # 这些在库里被 enrich 误标"互联网大厂"/混进互联网桶, 名单必须挡掉(不抬分)
    for noise in ["银泰百货", "国金证券", "平安证券", "招商基金", "平安科技", "华夏基金管理有限公司"]:
        assert internet_tier_of(noise) is None, noise


def test_curated_boost_values():
    assert _curated_internet_boost(SimpleNamespace(company="字节/抖音")) == 0.15
    assert _curated_internet_boost(SimpleNamespace(company="深度求索")) == 0.12
    assert _curated_internet_boost(SimpleNamespace(company="携程")) == 0.08
    assert _curated_internet_boost(SimpleNamespace(company="银泰百货")) == 0.0


def test_apply_quality_priors_floats_top_internet_over_noise():
    # 同基线分: tier1 真大厂应排在被误标的噪声公司之前
    bytedance = SimpleNamespace(company="字节/抖音", job_title="增长产品经理",
                                institution_tier="大厂", sub_category="用户/增长产品经理")
    yintai = SimpleNamespace(company="银泰百货", job_title="产品经理",
                             institution_tier="互联网大厂", sub_category="用户/增长产品经理")
    ranked = [(yintai, 0.50), (bytedance, 0.50)]
    out = dict((j.company, s) for j, s in apply_quality_priors(ranked))
    assert out["字节/抖音"] > out["银泰百货"]
