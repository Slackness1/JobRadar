"""Phase G T15 — 三维 cross 加权评分单元测试。"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from app.models import Job
from app.services.phase_g.recommendation_v2.scoring import (
    StudentProfile,
    freshness_quality_score,
    industry_overlap_score,
    rank_jobs,
    score_job,
    sub_cat_match_score,
    tier_overlap_score,
)


def _job(
    *,
    sub_category: str | None = None,
    sub_category_secondary: str | None = None,
    industry_focus: list[str] | None = None,
    institution_tier: str | None = None,
    quality_label: str = "good",
    sub_cat_confidence: float | None = 0.8,
    scraped_days_ago: int = 0,
) -> Job:
    return Job(
        job_id="x",
        company="X",
        sub_category=sub_category,
        sub_category_secondary=sub_category_secondary,
        industry_focus=json.dumps(industry_focus or [], ensure_ascii=False),
        institution_tier=institution_tier,
        quality_label=quality_label,
        sub_cat_confidence=sub_cat_confidence,
        scraped_at=datetime.utcnow() - timedelta(days=scraped_days_ago),
    )


# --- sub_cat_match_score ---

def test_sub_cat_primary_match_one():
    p = StudentProfile(preferred_sub_cats=["量化·中频"])
    assert sub_cat_match_score(p, _job(sub_category="量化·中频")) == 1.0


def test_sub_cat_secondary_match_zero_six():
    p = StudentProfile(preferred_sub_cats=["量化·中频"])
    j = _job(sub_category="公募权益", sub_category_secondary="量化·中频")
    assert sub_cat_match_score(p, j) == 0.6


def test_sub_cat_no_match_zero():
    p = StudentProfile(preferred_sub_cats=["量化·中频"])
    assert sub_cat_match_score(p, _job(sub_category="卖方研究员·TMT")) == 0.0


def test_sub_cat_no_preference_neutral_half():
    p = StudentProfile(preferred_sub_cats=[])
    assert sub_cat_match_score(p, _job(sub_category="量化·中频")) == 0.5


# --- industry_overlap_score ---

def test_industry_overlap_full():
    p = StudentProfile(preferred_industries=["A股权益", "消费"])
    j = _job(industry_focus=["A股权益", "消费", "TMT"])
    assert industry_overlap_score(p, j) == 1.0  # 2/2


def test_industry_overlap_partial():
    p = StudentProfile(preferred_industries=["A股权益", "消费", "TMT"])
    j = _job(industry_focus=["A股权益"])
    # overlap=1, preferred=3 → 1/3 ≈ 0.333
    assert abs(industry_overlap_score(p, j) - 1 / 3) < 0.01


def test_industry_overlap_zero():
    p = StudentProfile(preferred_industries=["A股权益"])
    j = _job(industry_focus=["TMT"])
    assert industry_overlap_score(p, j) == 0.0


def test_industry_overlap_no_pref_neutral():
    p = StudentProfile(preferred_industries=[])
    j = _job(industry_focus=["A股权益"])
    assert industry_overlap_score(p, j) == 0.5


def test_industry_overlap_json_parse_fail():
    p = StudentProfile(preferred_industries=["A股权益"])
    j = Job(job_id="x", industry_focus="not valid json")
    assert industry_overlap_score(p, j) == 0.3


# --- tier_overlap_score ---

def test_tier_hit_one():
    p = StudentProfile(preferred_tiers=["头部量化私募"])
    assert tier_overlap_score(p, _job(institution_tier="头部量化私募")) == 1.0


def test_tier_miss_low():
    p = StudentProfile(preferred_tiers=["头部量化私募"])
    assert tier_overlap_score(p, _job(institution_tier="互联网大厂")) == 0.2


def test_tier_job_no_tier():
    p = StudentProfile(preferred_tiers=["头部量化私募"])
    assert tier_overlap_score(p, _job(institution_tier=None)) == 0.3


def test_tier_no_pref_neutral():
    p = StudentProfile(preferred_tiers=[])
    assert tier_overlap_score(p, _job(institution_tier="头部量化私募")) == 0.5


# --- freshness_quality_score ---

def test_freshness_today_good_high_conf():
    j = _job(quality_label="good", sub_cat_confidence=0.9, scraped_days_ago=0)
    # fresh=1.0, qbonus=1.0, conf=0.9 → 0.5*1 + 0.3*1 + 0.2*0.9 = 0.98
    assert abs(freshness_quality_score(j) - 0.98) < 0.01


def test_freshness_30d_decays_to_zero():
    j = _job(quality_label="good", sub_cat_confidence=0.5, scraped_days_ago=30)
    # fresh=0.0, qbonus=1.0, conf=0.5 → 0 + 0.3 + 0.1 = 0.4
    assert abs(freshness_quality_score(j) - 0.4) < 0.01


def test_freshness_internship_lower_qbonus():
    j = _job(quality_label="internship_only", sub_cat_confidence=0.5, scraped_days_ago=0)
    # fresh=1.0, qbonus=0.6, conf=0.5 → 0.5 + 0.18 + 0.1 = 0.78
    assert abs(freshness_quality_score(j) - 0.78) < 0.01


# --- score_job 综合 ---

def test_score_job_perfect_match_around_one():
    p = StudentProfile(
        preferred_sub_cats=["量化·中频"],
        preferred_industries=["A股权益"],
        preferred_tiers=["头部量化私募"],
    )
    j = _job(
        sub_category="量化·中频",
        industry_focus=["A股权益"],
        institution_tier="头部量化私募",
        quality_label="good",
        sub_cat_confidence=1.0,
        scraped_days_ago=0,
    )
    # 0.5*1 + 0.25*1 + 0.15*1 + 0.10*1.0 = 1.0
    assert abs(score_job(p, j) - 1.0) < 0.01


def test_score_job_complete_miss_low():
    p = StudentProfile(
        preferred_sub_cats=["量化·中频"],
        preferred_industries=["A股权益"],
        preferred_tiers=["头部量化私募"],
    )
    j = _job(
        sub_category="卖方研究员·TMT",  # 不命中
        industry_focus=["TMT"],          # 不 overlap
        institution_tier="头部券商研究所",  # 不命中
        quality_label="low_signal",       # qbonus=0
        sub_cat_confidence=0.3,
        scraped_days_ago=20,
    )
    # 0.5*0 + 0.25*0 + 0.15*0.2 + 0.10*(0.5*(1-20/30) + 0.3*0 + 0.2*0.3)
    # = 0 + 0 + 0.03 + 0.1*(0.167+0+0.06) = 0.03 + 0.023 = 0.053
    score = score_job(p, j)
    assert score < 0.1


# --- rank_jobs ---

def test_rank_jobs_sorts_desc():
    p = StudentProfile(preferred_sub_cats=["量化·中频"])
    jobs = [
        _job(sub_category="卖方研究员·TMT"),       # primary miss
        _job(sub_category="量化·中频"),             # primary hit
        _job(sub_category="公募权益", sub_category_secondary="量化·中频"),  # secondary
    ]
    ranked = rank_jobs(p, jobs)
    assert ranked[0][0].sub_category == "量化·中频"
    assert ranked[1][0].sub_category == "公募权益"
    assert ranked[2][0].sub_category == "卖方研究员·TMT"
    # scores decreasing
    assert ranked[0][1] > ranked[1][1] > ranked[2][1]


def test_rank_jobs_empty_list():
    p = StudentProfile()
    assert rank_jobs(p, []) == []


def test_freshness_handles_tz_aware_scraped_at():
    """tz-aware scraped_at 不能让打分崩 (历史 bug: 整个 v2 崩→静默回落 v1→推荐跑偏)。"""
    from datetime import timezone

    job = Job(
        job_id="tz", company="X", sub_category="公募权益研究员",
        quality_label="good", sub_cat_confidence=0.8,
        scraped_at=datetime.now(timezone.utc),  # tz-aware
    )
    score = freshness_quality_score(job)  # 不应抛 TypeError
    assert 0.0 <= score <= 1.0

    profile = StudentProfile(
        preferred_sub_cats=["公募权益研究员"], preferred_industries=[], preferred_tiers=[],
    )
    # rank_jobs 跑全程不崩 (含 tz-aware 岗位)
    ranked = rank_jobs(profile, [job])
    assert len(ranked) == 1
