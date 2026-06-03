"""Phase G v2 — 三维 cross 加权评分。

公式:
  total = 0.50 * sub_cat_match + 0.25 * industry_overlap + 0.15 * tier_overlap + 0.10 * freshness_quality

  sub_cat_match (primary 1.0 / secondary 0.6 / miss 0.0 / 无偏好 0.5)
  industry_overlap (overlap / preferred 数; JSON 解析失败 0.3; 无偏好 0.5)
  tier_overlap (命中 1.0 / 无 tier 0.3 / 不命中 0.2; 无偏好 0.5)
  freshness_quality (0.5 freshness + 0.3 quality + 0.2 confidence)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime

from app.models import Job


@dataclass
class StudentProfile:
    preferred_sub_cats: list[str] = field(default_factory=list)
    preferred_industries: list[str] = field(default_factory=list)
    preferred_tiers: list[str] = field(default_factory=list)
    # 学生在确认页确认的细分方向(软信号)。空 = 不细化, 行为同现状。
    confirmed_sub_cats: list[str] = field(default_factory=list)


def sub_cat_match_score(profile: StudentProfile, job: Job) -> float:
    """软信号版:
    - 无 preferred → 0.5 neutral。
    - confirmed 为空 → primary 命中 preferred 1.0 / secondary 0.6 / miss 0.0(现状)。
    - confirmed 非空 → primary ∈ confirmed 1.0 / primary ∈ preferred 但未勾 0.5(降权不归零)
      / secondary ∈ confirmed 0.6 / 其余 0.0。
      注: 已确认后, secondary 只认 confirmed; secondary ∈ preferred 但未勾 → 0.0(故意不给次要信号续命)。
    """
    if not profile.preferred_sub_cats:
        return 0.5
    pref = set(profile.preferred_sub_cats)
    conf = set(profile.confirmed_sub_cats or [])
    primary = job.sub_category
    secondary = job.sub_category_secondary
    if not conf:
        if primary and primary in pref:
            return 1.0
        if secondary and secondary in pref:
            return 0.6
        return 0.0
    if primary and primary in conf:
        return 1.0
    if secondary and secondary in conf:
        return 0.6
    if primary and primary in pref:
        return 0.5
    return 0.0


def industry_overlap_score(profile: StudentProfile, job: Job) -> float:
    """preferred_industries 与 job.industry_focus (JSON array str) 的 overlap 比例。

    返回 overlap / max(1, len(preferred)),clipped to [0, 1]。
    JSON 解析失败给 0.3;无偏好 0.5 neutral。
    """
    if not profile.preferred_industries:
        return 0.5
    raw = job.industry_focus or "[]"
    try:
        job_industries = json.loads(raw)
        if not isinstance(job_industries, list):
            return 0.3
    except json.JSONDecodeError:
        return 0.3
    overlap = len(set(profile.preferred_industries) & set(job_industries))
    return min(1.0, overlap / max(1, len(profile.preferred_industries)))


def tier_overlap_score(profile: StudentProfile, job: Job) -> float:
    """institution_tier 命中 1.0,未命中 0.2,job 无 tier 0.3;无偏好 0.5。"""
    if not profile.preferred_tiers:
        return 0.5
    if not job.institution_tier:
        return 0.3
    return 1.0 if job.institution_tier in profile.preferred_tiers else 0.2


def freshness_quality_score(job: Job) -> float:
    """新鲜度 + quality_label + sub_cat_confidence 综合。

    fresh = max(0, 1 - days/30) (30 天内线性衰减,30 天外 0)
    qbonus = good 1.0 / internship_only 0.6 / 其它 0
    conf = sub_cat_confidence or 0.5
    total = 0.5*fresh + 0.3*qbonus + 0.2*conf
    """
    # SQLite 存 naive UTC,但个别源(增量入库/情报 ingest)写了 tz-aware 时间戳,
    # 直接和 naive utcnow() 相减会 TypeError → 整个 v2 打分崩 → 静默回落 v1
    # (= 真实简历推出来一堆跑偏的科技/运营岗)。这里把 scraped_at 归一成 naive。
    scraped = job.scraped_at
    if scraped is not None and scraped.tzinfo is not None:
        scraped = scraped.replace(tzinfo=None)
    days = (datetime.utcnow() - scraped).days if scraped else 30
    fresh = max(0.0, 1.0 - days / 30.0)
    qbonus = {"good": 1.0, "internship_only": 0.6}.get(job.quality_label or "", 0.0)
    conf = float(job.sub_cat_confidence or 0.5)
    return fresh * 0.5 + qbonus * 0.3 + conf * 0.2


def score_job(profile: StudentProfile, job: Job) -> float:
    """三维 cross 综合分: 0.5 sub + 0.25 industry + 0.15 tier + 0.10 freshness。"""
    return (
        0.50 * sub_cat_match_score(profile, job)
        + 0.25 * industry_overlap_score(profile, job)
        + 0.15 * tier_overlap_score(profile, job)
        + 0.10 * freshness_quality_score(job)
    )


def rank_jobs(profile: StudentProfile, jobs: list[Job]) -> list[tuple[Job, float]]:
    """按 score_job desc 排序, 返回 [(job, score), ...]。"""
    return sorted(
        ((j, score_job(profile, j)) for j in jobs),
        key=lambda x: -x[1],
    )
