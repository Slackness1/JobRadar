"""Phase G v2 recall — 替代 _build_track_condition (老 canonical_track-based)。

新逻辑:
- sub_category IS NOT NULL (T11/T12 enrich 过的才进推荐池)
- quality_label IN ('good', 'internship_only') (T10 backfill 过的)
- scraped_at > now - freshness_days
- preferred_sub_cats 非空时: primary 或 secondary 命中
- ORDER BY: primary 命中靠前, 然后 scraped_at desc
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Sequence

from sqlalchemy import and_, case, or_
from sqlalchemy.orm import Session

from app.models import Job


# 地点无关/全国类岗位：学生选了城市也应保留(可异地/远程/全国招)
_LOCATION_AGNOSTIC_KW = ("全国", "不限", "多地", "远程", "在家", "弹性办公", "anywhere", "remote")


def recall_candidates(
    db: Session,
    preferred_sub_cats: Sequence[str] = (),
    *,
    limit: int = 200,
    quality_labels: tuple[str, ...] = ("good", "internship_only"),
    freshness_days: int = 30,
    preferred_locations: Sequence[str] = (),
) -> list[Job]:
    """从 jobs 表拉 v2 推荐候选池。

    Args:
        db: SQLAlchemy session
        preferred_sub_cats: 用户偏好 sub_cat 列表 (从 profile 来), 空则不过滤 (拉全部 enriched 帖)
        limit: 最大返回条数
        quality_labels: 接受的 quality_label 集合, 默认 good + internship_only
        freshness_days: 仅 scraped_at 在最近 N 天内

    Returns:
        list of Job, 已按 (primary 命中 desc, scraped_at desc) 排序。
    """
    cutoff = datetime.utcnow() - timedelta(days=freshness_days)
    conds = [
        Job.sub_category.isnot(None),
        Job.quality_label.in_(quality_labels),
        Job.scraped_at > cutoff,
        # dead 链不入推荐池 (alive 或 NULL 才行)
        or_(Job.link_status == "alive", Job.link_status.is_(None)),
    ]
    if preferred_sub_cats:
        sub_list = list(preferred_sub_cats)
        conds.append(
            or_(
                Job.sub_category.in_(sub_list),
                Job.sub_category_secondary.in_(sub_list),
            )
        )

    # 地点过滤：学生选了城市(如北京/上海)就只召回 命中城市 OR 地点无关(全国/远程/未知)
    # 的岗,踢掉明显异地(深圳/福州/日本)。location 字段脏(可能 "上海,深圳"/"上海·浦东"),
    # 用 LIKE 子串匹配。空 preferred_locations 不过滤。
    locs = [str(c).strip() for c in (preferred_locations or []) if str(c).strip()]
    if locs:
        loc_conds = [Job.location.is_(None), Job.location == ""]
        for kw in _LOCATION_AGNOSTIC_KW:
            loc_conds.append(Job.location.like(f"%{kw}%"))
        for city in locs:
            loc_conds.append(Job.location.like(f"%{city}%"))
        conds.append(or_(*loc_conds))

    query = db.query(Job).filter(and_(*conds))

    if preferred_sub_cats:
        # primary 命中的排在前面 (用 CASE WHEN)
        is_primary = case(
            (Job.sub_category.in_(list(preferred_sub_cats)), 1), else_=0
        )
        query = query.order_by(is_primary.desc(), Job.scraped_at.desc())
    else:
        query = query.order_by(Job.scraped_at.desc())

    return query.limit(limit).all()
