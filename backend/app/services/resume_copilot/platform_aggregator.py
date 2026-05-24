"""Phase 3 (2026-05-24) — 把推荐 items 按公司聚合成"平台卡片"列表。

Why: top-N items 里同公司岗位经常重复 5-7 次(实测 P1 林思远招商基金占 top 10
的 7 个),用户体验是"翻 10 页都是同一家公司"。聚合成平台卡片后,左侧 rail 只
显示 N 张公司卡,展开后才看到该公司下的 top-3 岗位。

不重新跑 LLM rerank — 输入是已经排好的 ResumeRecommendationItem list。
"""
from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm import Session

from app.schemas_resume_copilot import (
    ResumeRecommendationItem,
    ResumeRecommendationPlatform,
    ResumeRecommendationPlatformJobBrief,
)


_PRIORITY_LETTER_RANK = {"A": 4, "B": 3, "C": 2, "D": 1, "": 0}
_TIER_LABEL_RANK = {"强匹配": 3, "可迁移": 2, "有差距": 1, "": 0}


def _best_letter(letters: Iterable[str]) -> str:
    best = ""
    best_rank = 0
    for L in letters:
        r = _PRIORITY_LETTER_RANK.get(L, 0)
        if r > best_rank:
            best, best_rank = L, r
    return best


def _best_tier(tiers: Iterable[str]) -> str:
    best = ""
    best_rank = 0
    for T in tiers:
        r = _TIER_LABEL_RANK.get(T, 0)
        if r > best_rank:
            best, best_rank = T, r
    return best


def _best_match_kind(kinds: Iterable[str]) -> str:
    """hit / null_hit > transferable > ambiguous > mismatch > no_pref/''。

    用 _classify_track_match 同款优先级,跟 _track_kind_to_tier_label 对齐。
    """
    rank = {"hit": 5, "null_hit": 5, "transferable": 4, "ambiguous": 3,
            "no_pref": 2, "mismatch": 1, "": 0}
    best = ""
    best_rank = 0
    for k in kinds:
        r = rank.get(k, 0)
        if r > best_rank:
            best, best_rank = k, r
    return best


def aggregate_by_company(
    items: list[ResumeRecommendationItem],
    *,
    db: Session | None = None,
    top_jobs_per_platform: int = 3,
) -> list[ResumeRecommendationPlatform]:
    """Group recommendation items by `company`, return sorted platform cards.

    Sort:
      1. platform_score (max final_score) desc
      2. n_jobs desc — 平台开放岗位多优先
      3. company asc — 稳定

    n_xhs_insights:同辈情报数量,来自 XHS 知识库 company_target 命中数。
    db=None 时跳过(用于纯单元测试)。
    """
    if not items:
        return []

    groups: dict[str, list[ResumeRecommendationItem]] = {}
    for item in items:
        key = (item.company or "").strip()
        if not key:
            continue
        groups.setdefault(key, []).append(item)

    # 顺手把 XHS insight 计数批量拉一遍,避免 N+1。
    n_insights_by_company: dict[str, int] = {}
    if db is not None and groups:
        try:
            from app.services.xhs.retrieve import count_by_company
            n_insights_by_company = count_by_company(db, list(groups.keys()))
        except Exception:
            n_insights_by_company = {}

    platforms: list[ResumeRecommendationPlatform] = []
    for company, jobs in groups.items():
        sorted_jobs = sorted(jobs, key=lambda j: j.final_score, reverse=True)
        top_jobs = [
            ResumeRecommendationPlatformJobBrief(
                job_id=j.job_id,
                job_title=j.job_title,
                final_score=j.final_score,
                priority_letter=j.priority_letter,
                tier_label=j.tier_label,
                is_internship=j.is_internship,
                location=j.location,
                detail_url=j.detail_url,
            )
            for j in sorted_jobs[:top_jobs_per_platform]
        ]
        # 优先用最高分 job 的 priority_tier_label 作为平台 brand 标签 —
        # 同公司不同岗位 priority_tier 一般一致,但万一不一致取分最高的。
        brand_label = sorted_jobs[0].company_priority_label
        brand_tier = sorted_jobs[0].company_priority_tier
        # 用最高分 job 的 matched_track_label
        matched_track = sorted_jobs[0].matched_track_label

        platforms.append(
            ResumeRecommendationPlatform(
                company=company,
                company_priority_label=brand_label,
                company_priority_tier=brand_tier,
                platform_score=sorted_jobs[0].final_score,
                n_jobs=len(jobs),
                n_campus=sum(1 for j in jobs if not j.is_internship),
                n_internship=sum(1 for j in jobs if j.is_internship),
                n_xhs_insights=int(n_insights_by_company.get(company, 0)),
                track_match_kind=_best_match_kind(j.track_match_kind for j in jobs),
                priority_letter=_best_letter(j.priority_letter for j in jobs),
                tier_label=_best_tier(j.tier_label for j in jobs),
                matched_track_label=matched_track,
                top_jobs=top_jobs,
                all_job_ids=[j.job_id for j in sorted_jobs],
            )
        )

    platforms.sort(
        key=lambda p: (p.platform_score, p.n_jobs, p.company),
        reverse=False,  # 反过来取 sort key 再 reverse 让 string asc + ints desc
    )
    # 上一步是 ascending 全排; 我们要 score desc → n_jobs desc → company asc
    platforms.sort(key=lambda p: (-p.platform_score, -p.n_jobs, p.company))
    return platforms
