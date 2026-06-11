"""GT 平台公司质量先验 — Hub feed 桶内排序根治。

三维评分里 行业/梯队 两维恒中性(profile 无该字段), 桶内真研究岗之间本只剩新鲜度
区分 → 新爬的小机构岗会盖过经过策展的平台公司。search_candidates 加 +0.15 GT 先验
后, 平台公司(GT)即便更旧也应排在非 GT 新岗之上。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Job
from app.services.resume_copilot.recommend_search import _gt_quality_boost, search_candidates
from app.services.resume_copilot.working_query import WorkingQuery


def _build_session_factory() -> sessionmaker:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    sl = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return sl


class _FakeJob:
    def __init__(self, company: str, sub_category: str) -> None:
        self.company = company
        self.sub_category = sub_category


def test_gt_quality_boost_only_for_gt_company():
    # 华夏基金 是「公募权益研究员」的 ground_truth 平台公司 → +0.15
    assert _gt_quality_boost(_FakeJob("华夏基金", "公募权益研究员")) == 0.15
    # 非 GT 小机构 → 0
    assert _gt_quality_boost(_FakeJob("某不知名资本", "公募权益研究员")) == 0.0
    # 缺 sub_cat / 缺公司 → 0(不崩)
    assert _gt_quality_boost(_FakeJob("华夏基金", "")) == 0.0
    assert _gt_quality_boost(_FakeJob("", "公募权益研究员")) == 0.0


def _add_job(db: Session, *, job_id: str, company: str, sub_cat: str, days_old: int) -> None:
    db.add(
        Job(
            job_id=job_id,
            company=company,
            job_title="研究员",
            job_req="x",
            job_duty="x",
            sub_category=sub_cat,
            quality_label="good",
            scraped_at=datetime.utcnow() - timedelta(days=days_old),
        )
    )


def test_gt_company_outranks_fresher_non_gt_in_same_bucket():
    sl = _build_session_factory()
    db = sl()
    try:
        sub = "公募权益研究员"
        # GT 平台公司, 旧 10 天
        _add_job(db, job_id="gt-old", company="华夏基金", sub_cat=sub, days_old=10)
        # 非 GT 小机构, 今天刚爬(更新鲜)
        _add_job(db, job_id="nongt-fresh", company="某不知名资本", sub_cat=sub, days_old=0)
        db.commit()

        q = WorkingQuery(seed_sub_cats=[sub])
        items = search_candidates(db, q, limit=10)
        companies = [str(getattr(it, "company", "")) for it in items]
        assert "华夏基金" in companies and "某不知名资本" in companies
        # GT 平台公司即便更旧, 也排在非 GT 新岗之前(质量先验盖过新鲜度)
        assert companies.index("华夏基金") < companies.index("某不知名资本")
    finally:
        db.close()
