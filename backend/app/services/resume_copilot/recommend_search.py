"""search_candidates tool — 按 WorkingQuery 从库召回 + 规则排 + 后处理(置顶/过滤)。
纯规则、秒级、**不调 LLM**。feed item 沿用 recommendation_v2 的 ResumeRecommendationItem。

铁律: 本模块永不触发 Pro rerank / narrative 生成 / 任何 LLM client。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.services.resume_copilot.working_query import WorkingQuery

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _fresh_key(job: Any) -> datetime:
    """sort=='fresh' 排序键。scraped_at 在库里 naive/aware 混存(SQLite 存 naive UTC,
    部分行带 tz) → 统一归一到 aware UTC, 缺失退回 epoch, 避免 naive/aware 比较崩。"""
    ts = getattr(job, "scraped_at", None)
    if not isinstance(ts, datetime):
        return _EPOCH
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


def _company_text(it: Any) -> str:
    return str(getattr(it, "company", "") or "")


def _sub_text(it: Any) -> str:
    return str(getattr(it, "matched_track_label", "") or "")


def _apply_exclude(feed: list, exclude: list[str]) -> list:
    if not exclude:
        return feed

    def hit(it):
        text = f"{_company_text(it)} {_sub_text(it)}"
        return any(x and x in text for x in exclude)

    return [it for it in feed if not hit(it)]


def _apply_company_pref(feed: list, companies: list[str], only: bool) -> list:
    if not companies:
        return feed

    def hit(it):
        comp = _company_text(it)
        return any(c and c in comp for c in companies)

    preferred = [it for it in feed if hit(it)]
    if only:
        return preferred
    rest = [it for it in feed if not hit(it)]
    return preferred + rest  # 置顶, 保留其余(不藏岗)


def _tag_rule_item(it: Any) -> Any:
    """标注本条是纯规则产出: used_ai=False, enhanced_score 不超过规则 base 分。
    base_match_score(0-100, 规则分)已由 _v2_items_from_ranked 填好, 这里只保证
    没有任何 AI 增强痕迹遗留。"""
    setattr(it, "used_ai", False)
    setattr(it, "enhanced_score", getattr(it, "base_match_score", 0))
    return it


def search_candidates(db: Session, query: WorkingQuery, *, limit: int = 40) -> list:
    """WorkingQuery → ranked feed(list[ResumeRecommendationItem])。纯规则、秒级、不调 LLM。"""
    from app.services.phase_g.recommendation_v2 import recall as _recall, scoring as _scoring
    from app.services.resume_copilot.recommendation import _v2_items_from_ranked

    eff = query.effective_sub_cats()
    jobs = _recall.recall_candidates(
        db,
        eff,
        limit=max(limit * 4, 80),
        preferred_locations=query.locations,
    )
    profile = _scoring.StudentProfile(
        preferred_sub_cats=eff,
        confirmed_sub_cats=list(query.seed_sub_cats),
    )
    ranked = _scoring.rank_jobs(profile, jobs)  # [(job, score 0-1), ...]
    if query.sort == "fresh":
        ranked = sorted(ranked, key=lambda t: _fresh_key(t[0]), reverse=True)
    # sort=='pay' 暂无可靠薪资字段 → 退回 match 序

    # _v2_items_from_ranked 期望 list[dict]: 每条含 job / final_score / base_score (0-1)。
    # 纯规则模式无 LLM rerank → final == base == 规则分。
    ranked_dicts = [
        {"job": j, "final_score": s, "base_score": s} for j, s in ranked[: limit * 2]
    ]
    items = _v2_items_from_ranked(ranked_dicts, eff, None)
    items = [_tag_rule_item(it) for it in items]
    items = _apply_exclude(items, query.exclude)
    items = _apply_company_pref(items, query.companies, query.only)
    return items[:limit]
