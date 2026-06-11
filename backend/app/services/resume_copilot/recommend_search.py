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

# 研究/投资类桶里的中后台支持岗误配词(非研究/投资本职)。命中则桶内降权沉底。
# 区别于 taxonomy.quality.is_low_quality_role(那组覆盖零售/销售,在 quality_label 阶段已过滤)。
_SUPPORT_ROLE_HINTS = (
    "反洗钱", "风险岗", "风控岗", "风险管理岗", "合规岗", "合规经理", "内控", "稽核",
    "投融类", "运营岗", "中后台", "清算", "结算", "估值核算", "登记结算",
    "财务岗", "出纳", "行政", "人力资源", "招聘", "档案", "信息技术运维", "网络运维",
)


def _is_support_role(title: str) -> bool:
    return any(h in title for h in _SUPPORT_ROLE_HINTS)


def _gt_quality_boost(job: Any) -> float:
    """GT 平台公司质量先验: 岗位公司 ∈ 该 sub_cat 的 ground_truth 平台公司集 → +0.15。

    动机(根治桶内乱序): 三维评分里 行业/梯队 两维恒中性(profile 无该字段, 见下方
    ranked 注释), 桶内真研究岗之间只剩新鲜度(0.10)区分 → 新爬的小机构岗会盖过经过
    策展的平台公司(中金/幻方/中欧 等)。学生对"档次"没有可填的偏好, 但所有人都想去
    更好的平台 → 用 ground_truth 这个**干净的二元信号**做统一质量先验, 让平台公司
    浮到桶内前列, 而非单纯按谁新排。比拿 institution_tier 自由文本(头部券商/大厂/
    中型券商研究所… 70+ 杂值)硬映射稳, 符合"逻辑越简单耐用越好"。
    """
    sc = str(getattr(job, "sub_category", "") or "")
    if not sc:
        return 0.0
    from app.services.phase_g.tier_fit.platform_skeleton import (
        _norm_company,
        gt_companies_for_sub_cat,
    )
    comp = _norm_company(str(getattr(job, "company", "") or ""))
    if not comp:
        return 0.0
    return 0.15 if comp in gt_companies_for_sub_cat(sc) else 0.0


# institution_tier 档次退路 —— GT 名单是金融导向(SAIF), 互联网/非 GT 金融桶里 GT 集
# 为空, 此时桶内只剩新鲜度区分(同 finance 改前的"破岗位")。enrich 时已给每个岗打了
# institution_tier(大厂/互联网大厂/独角兽/头部券商…), 拿它做退路: 头部档浮顶。
# 关键词匹配, 不硬编公司名 —— 互联网(大厂/独角兽)与非 GT 金融(头部/一线/外资)通用。
_TOP_TIER_HINTS = ("大厂", "头部", "一线", "外资", "独角兽", "头部电商", "央企")
_MID_TIER_HINTS = ("腰部", "中型", "二线", "次头部")


def _tier_quality_boost(job: Any) -> float:
    """institution_tier → 桶内档次加分(仅 GT 空时作退路)。头部 +0.12 / 腰部 +0.04。"""
    t = str(getattr(job, "institution_tier", "") or "")
    if not t:
        return 0.0
    if any(h in t for h in _TOP_TIER_HINTS):
        return 0.12
    if any(h in t for h in _MID_TIER_HINTS):
        return 0.04
    return 0.0


def apply_quality_priors(ranked: list[tuple[Any, float]]) -> list[tuple[Any, float]]:
    """对 [(job, score 0-1)] 施加桶内质量先验, 仅调分不排序(调用方自行 sort):
      - support 岗 -0.30 沉底(研究/投资桶里的中后台误配)
      - GT 平台公司 +0.15 浮顶(经过策展的好平台压过随机新岗)
      - GT 集为空的桶(互联网 PM / 非 GT 金融)退到 institution_tier 档次加分,
        让大厂/头部浮顶, 而非只按新鲜度排(修互联网赛道"破岗位")
    两条推荐路径共用 —— Hub 快路(search_candidates)与旧 generate 慢路语义一致。
    """
    out: list[tuple[Any, float]] = []
    for j, s in ranked:
        adj = s
        if _is_support_role(str(getattr(j, "job_title", "") or "")):
            adj -= 0.30
        gt = _gt_quality_boost(j)
        # GT 命中用策展信号(+0.15); 否则退到 institution_tier 档次, 二者不叠加。
        adj += gt if gt > 0 else _tier_quality_boost(j)
        out.append((j, adj))
    return out


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
    # 桶内排序质量先验(support 沉底 + GT 平台浮顶), 与旧 generate 慢路共用同一函数。
    ranked = apply_quality_priors(ranked)
    if query.sort == "fresh":
        ranked = sorted(ranked, key=lambda t: _fresh_key(t[0]), reverse=True)
    else:
        ranked = sorted(ranked, key=lambda t: t[1], reverse=True)
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
