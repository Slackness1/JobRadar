"""Phase 3 (2026-05-24) — platform aggregator 单测。

覆盖:
  - 多公司分组 + 按 platform_score 排序
  - top_jobs 取 top 3 by final_score
  - n_campus / n_internship 计数
  - priority_letter / tier_label 取最佳
  - 空 items / 空公司名 跳过
  - all_job_ids 全量保留
"""
from __future__ import annotations

from app.schemas_resume_copilot import ResumeRecommendationItem
from app.services.resume_copilot.platform_aggregator import aggregate_by_company


def _item(**kw) -> ResumeRecommendationItem:
    defaults = dict(
        job_id="j",
        company="X",
        job_title="t",
        location="上海",
        detail_url="",
        objective_score=0,
        preference_score=0,
        base_job_score=0,
        company_priority_score=0,
        base_match_score=0,
        enhanced_score=0,
        final_score=50,
        matched_track_label="",
        matched_track_key="",
        matched_role_family="",
        company_priority_tier="",
        company_priority_label="",
        topic_key="",
        used_ai=False,
        why_recommended=[],
        strengths=[],
        risks=[],
        tier_label="",
        priority_letter="",
        track_match_kind="",
        is_internship=False,
    )
    defaults.update(kw)
    return ResumeRecommendationItem(**defaults)


def test_groups_by_company_and_sorts_by_platform_score():
    items = [
        _item(job_id="j1", company="招商基金", final_score=66),
        _item(job_id="j2", company="招商基金", final_score=60),
        _item(job_id="j3", company="东吴证券", final_score=70),
        _item(job_id="j4", company="嘉实基金", final_score=60),
    ]
    out = aggregate_by_company(items)
    assert [p.company for p in out] == ["东吴证券", "招商基金", "嘉实基金"]
    assert out[0].platform_score == 70 and out[0].n_jobs == 1
    assert out[1].platform_score == 66 and out[1].n_jobs == 2
    assert out[2].platform_score == 60 and out[2].n_jobs == 1


def test_top_jobs_picks_top_3_by_score():
    items = [
        _item(job_id=f"j{i}", company="招商基金", final_score=70 - i)
        for i in range(5)
    ]
    out = aggregate_by_company(items)
    assert len(out) == 1
    assert [j.job_id for j in out[0].top_jobs] == ["j0", "j1", "j2"]
    assert out[0].all_job_ids == ["j0", "j1", "j2", "j3", "j4"]


def test_counts_campus_vs_internship():
    items = [
        _item(job_id="j1", company="X", final_score=60, is_internship=False),
        _item(job_id="j2", company="X", final_score=55, is_internship=True),
        _item(job_id="j3", company="X", final_score=50, is_internship=True),
    ]
    out = aggregate_by_company(items)
    assert out[0].n_jobs == 3
    assert out[0].n_campus == 1
    assert out[0].n_internship == 2


def test_priority_letter_picks_best():
    items = [
        _item(job_id="j1", company="X", final_score=70, priority_letter="C"),
        _item(job_id="j2", company="X", final_score=80, priority_letter="A"),
        _item(job_id="j3", company="X", final_score=60, priority_letter="B"),
    ]
    out = aggregate_by_company(items)
    assert out[0].priority_letter == "A"


def test_tier_label_picks_best():
    items = [
        _item(job_id="j1", company="X", final_score=70, tier_label="有差距"),
        _item(job_id="j2", company="X", final_score=60, tier_label="强匹配"),
        _item(job_id="j3", company="X", final_score=50, tier_label="可迁移"),
    ]
    out = aggregate_by_company(items)
    assert out[0].tier_label == "强匹配"


def test_track_match_kind_picks_best():
    items = [
        _item(job_id="j1", company="X", final_score=70, track_match_kind="mismatch"),
        _item(job_id="j2", company="X", final_score=60, track_match_kind="hit"),
        _item(job_id="j3", company="X", final_score=50, track_match_kind="transferable"),
    ]
    out = aggregate_by_company(items)
    assert out[0].track_match_kind == "hit"


def test_brand_taken_from_highest_score_job():
    items = [
        _item(job_id="j1", company="X", final_score=70,
              company_priority_label="T0", company_priority_tier="funds:tier1",
              matched_track_label="二级买方·基本面"),
        _item(job_id="j2", company="X", final_score=60,
              company_priority_label="T2", company_priority_tier="funds:tier2",
              matched_track_label=""),
    ]
    out = aggregate_by_company(items)
    assert out[0].company_priority_label == "T0"
    assert out[0].matched_track_label == "二级买方·基本面"


def test_empty_items_returns_empty():
    assert aggregate_by_company([]) == []


def test_blank_company_skipped():
    items = [
        _item(job_id="j1", company="", final_score=70),
        _item(job_id="j2", company="招商基金", final_score=60),
    ]
    out = aggregate_by_company(items)
    assert len(out) == 1
    assert out[0].company == "招商基金"


def test_tie_break_uses_n_jobs_then_company():
    """同 platform_score 时 n_jobs 多的优先, 再按 company asc。"""
    items = [
        _item(job_id="j1", company="A", final_score=66),
        _item(job_id="j2", company="B", final_score=66),
        _item(job_id="j3", company="B", final_score=60),
    ]
    out = aggregate_by_company(items)
    # B 有 2 个 jobs vs A 1 个 → B 优先
    assert [p.company for p in out] == ["B", "A"]
