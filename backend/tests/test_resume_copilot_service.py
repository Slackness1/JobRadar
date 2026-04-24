from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Job, JobIntelSnapshot, ResumeCopilotSession, ResumeRecommendationItem, ResumeTopicCache
from app.services.resume_copilot.recommender import build_recommendation_run, normalize_preferences


def _new_db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    testing_session_local = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    return testing_session_local()


def _add_job(
    db,
    *,
    job_id: str,
    company: str,
    title: str,
    location: str,
    job_req: str,
    major_req: str = "",
    job_stage: str = "campus",
):
    job = Job(
        job_id=job_id,
        source="official",
        company=company,
        company_type_industry="",
        company_tags="",
        department="",
        job_title=title,
        location=location,
        major_req=major_req,
        job_req=job_req,
        job_duty=job_req,
        application_status="待申请",
        job_stage=job_stage,
        source_config_id="test",
        publish_date=datetime.utcnow() - timedelta(days=3),
        detail_url=f"https://example.com/{job_id}",
    )
    db.add(job)
    db.flush()
    return job


def test_build_recommendation_run_prioritizes_top_platforms_and_uses_topic_cache():
    db = _new_db_session()
    try:
        tencent = _add_job(
            db,
            job_id="job-1",
            company="腾讯科技",
            title="数据分析岗",
            location="上海",
            job_req="本科及以上，熟悉 Python、SQL、数据分析，负责业务分析与策略支持",
            major_req="统计学、计算机相关专业",
        )
        _add_job(
            db,
            job_id="job-2",
            company="某普通科技公司",
            title="数据分析岗",
            location="上海",
            job_req="本科及以上，熟悉 Python、SQL、数据分析",
            major_req="统计学、计算机相关专业",
        )
        cicc = _add_job(
            db,
            job_id="job-3",
            company="中金公司",
            title="行业研究助理",
            location="上海",
            job_req="硕士优先，负责行业研究、资料整理、深度报告撰写",
            major_req="金融、经济、管理相关专业",
        )
        db.add(
            JobIntelSnapshot(
                job_id=tencent.id,
                snapshot_type="interview",
                summary_text="历史情报显示团队偏数据策略，培养路径较清晰。",
                evidence_count=3,
                source_platforms_json='["xiaohongshu"]',
                confidence_score=0.8,
            )
        )
        db.flush()

        session = ResumeCopilotSession(filename="resume.pdf", resume_text="mock")
        db.add(session)
        db.flush()

        profile = {
            "education_level": "硕士",
            "education_rank": 3,
            "major_tags": ["数学统计", "计算机"],
            "skill_tags": ["python", "sql", "research_writing"],
            "function_tags": ["data", "research"],
            "keyword_tags": ["python", "sql"],
            "summary": "硕士，偏数据与研究。",
        }
        preferences = normalize_preferences(
            {
                "preferred_tracks": ["internet", "securities"],
                "preferred_cities": ["上海"],
                "preferred_functions": ["data", "research"],
                "accept_relocation": False,
                "max_results": 5,
                "prioritize_top_platforms": True,
            }
        )

        run = build_recommendation_run(db, session.id, profile, preferences)
        db.commit()

        items = (
            db.query(ResumeRecommendationItem, Job)
            .join(Job, Job.id == ResumeRecommendationItem.job_id)
            .filter(ResumeRecommendationItem.run_id == run.id)
            .order_by(ResumeRecommendationItem.final_score.desc())
            .all()
        )

        assert [job.company for _item, job in items[:2]] == ["腾讯科技", "中金公司"]

        tencent_item = next(item for item, job in items if job.company == "腾讯科技")
        cicc_item = next(item for item, job in items if job.company == "中金公司")

        assert tencent_item.topic_cache_status == "ready"
        assert tencent_item.enhanced_score >= tencent_item.base_score
        assert tencent_item.topic_summary
        assert cicc_item.need_enrichment is True
        assert "high_info_asymmetry" in cicc_item.enrichment_reason

        cache_rows = db.query(ResumeTopicCache).all()
        assert len(cache_rows) >= 2
    finally:
        db.close()
