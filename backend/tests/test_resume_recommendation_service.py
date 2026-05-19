from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Job, JobScore, Track
from app.schemas_resume_copilot import (
    ResumePreferencePayload,
    ResumeProfilePayload,
    ResumeRecommendationItem,
    ResumeSkillsPayload,
)
from app.services.resume_copilot.recommendation import (
    recommend_jobs_for_profile as _recommend_jobs_for_profile,
)


def recommend_jobs_for_profile(*args, **kwargs):
    """Test-only wrapper: disable the BE-3 top-10/50-floor by default so the
    unit-level scoring contracts (token match, preference boost, AI rerank,
    ...) can be asserted in isolation. Tests that exercise the threshold/
    top-N behaviour itself live in ``test_recommend_threshold.py``."""
    kwargs.setdefault('min_score', 0)
    kwargs.setdefault('top_n', 999)
    return _recommend_jobs_for_profile(*args, **kwargs)


def _build_session_factory():
    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return testing_session_local


def _build_profile(**overrides) -> ResumeProfilePayload:
    payload = {
        'basic_info': {'name': 'Jane Doe'},
        'education': [],
        'internships': [],
        'projects': [],
        'skills': ResumeSkillsPayload(technical=['Python', 'SQL'], tools=['Git'], languages=[]),
        'languages': ['English'],
        'awards': [],
        'candidate_summary': 'Backend-focused builder',
        'inferred_roles': ['Backend Engineer'],
        'inferred_tracks': ['Internet'],
    }
    payload.update(overrides)
    return ResumeProfilePayload.model_validate(payload)


def _build_preferences(**overrides) -> ResumePreferencePayload:
    payload = {
        'preferred_tracks': [],
        'preferred_locations': [],
        'preferred_roles': [],
        'preferred_company_types': [],
        'accept_relocation': False,
        'accept_internship': False,
        'campus_only': False,
        'social_ok': False,
        'preference_notes': '',
        'all_skipped': False,
    }
    payload.update(overrides)
    return ResumePreferencePayload.model_validate(payload)


def _add_job(db: Session, **overrides) -> Job:
    job = Job(
        job_id=overrides.get('job_id', 'job-1'),
        company=overrides.get('company', 'Example Co'),
        company_type_industry=overrides.get('company_type_industry', 'Internet'),
        department=overrides.get('department', 'Engineering'),
        job_title=overrides.get('job_title', 'Backend Engineer'),
        location=overrides.get('location', 'Shanghai'),
        major_req=overrides.get('major_req', 'Computer Science'),
        job_req=overrides.get('job_req', 'Python SQL APIs'),
        job_duty=overrides.get('job_duty', 'Build backend services'),
        job_stage=overrides.get('job_stage', 'campus'),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _add_job_score(db: Session, job: Job, track_name: str, score: int) -> None:
    track = Track(key=track_name.lower(), name=track_name, weight=1.0, min_score=0, sort_order=0)
    db.add(track)
    db.commit()
    db.refresh(track)

    db.add(JobScore(job_id=job.id, track_id=track.id, score=score, matched_keywords='[]'))
    db.commit()


def test_recommend_jobs_prefers_jobs_matching_skills_and_inferred_roles():
    session_factory = _build_session_factory()
    db = session_factory()
    try:
        strong_match = _add_job(
            db,
            job_id='job-strong',
            company='Alpha',
            job_title='Backend Engineer',
            job_req='Python SQL distributed systems',
            job_duty='Build backend APIs and data pipelines',
        )
        weak_match = _add_job(
            db,
            job_id='job-weak',
            company='Beta',
            job_title='Operations Analyst',
            job_req='Excel reporting coordination',
            job_duty='Handle operations reporting',
        )

        recommendations, _, _ = recommend_jobs_for_profile(db, _build_profile(), _build_preferences())

        assert [item.job_id for item in recommendations[:2]] == [strong_match.job_id, weak_match.job_id]
        assert recommendations[0].objective_score > recommendations[1].objective_score
        assert recommendations[0].base_match_score > recommendations[1].base_match_score
        assert recommendations[0].used_ai is False
        assert '匹配方向：Backend Engineer' in recommendations[0].why_recommended
        assert isinstance(recommendations[0], ResumeRecommendationItem)
    finally:
        db.close()


def test_preference_scoring_is_a_soft_boost_not_a_filter():
    session_factory = _build_session_factory()
    db = session_factory()
    try:
        preferred_job = _add_job(
            db,
            job_id='job-preferred',
            company='Alpha',
            location='Shanghai',
            company_type_industry='Internet',
            job_title='Backend Engineer',
            job_req='Python services',
        )
        non_preferred_job = _add_job(
            db,
            job_id='job-non-preferred',
            company='Beta',
            location='Beijing',
            company_type_industry='Manufacturing',
            job_title='Backend Engineer',
            job_req='Python platform work',
        )

        recommendations, _, _ = recommend_jobs_for_profile(
            db,
            _build_profile(),
            _build_preferences(preferred_locations=['Shanghai'], preferred_company_types=['Internet']),
        )

        indexed = {item.job_id: item for item in recommendations}
        assert set(indexed) == {preferred_job.job_id, non_preferred_job.job_id}
        assert indexed[preferred_job.job_id].preference_score > indexed[non_preferred_job.job_id].preference_score
        assert indexed[non_preferred_job.job_id].preference_score == 0
    finally:
        db.close()


def test_all_skipped_ignores_preference_boosts():
    session_factory = _build_session_factory()
    db = session_factory()
    try:
        preferred_job = _add_job(
            db,
            job_id='job-preferred',
            company='Alpha',
            location='Shanghai',
            company_type_industry='Internet',
        )
        _add_job(
            db,
            job_id='job-other',
            company='Beta',
            location='Beijing',
            company_type_industry='Manufacturing',
        )

        active_preferences, _, _ = recommend_jobs_for_profile(
            db,
            _build_profile(),
            _build_preferences(preferred_locations=['Shanghai'], preferred_company_types=['Internet']),
        )
        skipped_preferences, _, _ = recommend_jobs_for_profile(
            db,
            _build_profile(),
            _build_preferences(
                preferred_locations=['Shanghai'],
                preferred_company_types=['Internet'],
                all_skipped=True,
            ),
        )

        active_item = next(item for item in active_preferences if item.job_id == preferred_job.job_id)
        skipped_item = next(item for item in skipped_preferences if item.job_id == preferred_job.job_id)
        assert active_item.preference_score > 0
        assert skipped_item.preference_score == 0
    finally:
        db.close()


def test_existing_job_scores_contribute_base_signal():
    session_factory = _build_session_factory()
    db = session_factory()
    try:
        scored_job = _add_job(
            db,
            job_id='job-scored',
            company='Alpha',
            job_title='Generalist Role',
            job_req='Communication and coordination',
            job_duty='Cross-functional support',
        )
        unscored_job = _add_job(
            db,
            job_id='job-unscored',
            company='Beta',
            job_title='Generalist Role',
            job_req='Communication and coordination',
            job_duty='Cross-functional support',
        )
        _add_job_score(db, scored_job, 'Internet', 72)

        recommendations, _, _ = recommend_jobs_for_profile(
            db,
            _build_profile(inferred_roles=[''], skills=ResumeSkillsPayload(technical=[], tools=[], languages=[])),
            _build_preferences(all_skipped=True),
        )

        indexed = {item.job_id: item for item in recommendations}
        assert indexed[scored_job.job_id].base_job_score == 72
        assert indexed[unscored_job.job_id].base_job_score == 0
        assert indexed[scored_job.job_id].base_match_score > indexed[unscored_job.job_id].base_match_score
        assert indexed[scored_job.job_id].final_score == indexed[scored_job.job_id].base_match_score
    finally:
        db.close()


def test_base_job_score_prefers_scores_for_inferred_tracks_only():
    session_factory = _build_session_factory()
    db = session_factory()
    try:
        relevant_job = _add_job(
            db,
            job_id='job-relevant-track',
            company='Alpha',
            job_title='Generalist Role',
            company_type_industry='Internet',
        )
        irrelevant_job = _add_job(
            db,
            job_id='job-irrelevant-track',
            company='Beta',
            job_title='Generalist Role',
            company_type_industry='Manufacturing',
        )
        _add_job_score(db, relevant_job, 'Internet', 24)
        _add_job_score(db, irrelevant_job, 'Manufacturing', 80)

        recommendations, _, _ = recommend_jobs_for_profile(
            db,
            _build_profile(
                inferred_tracks=['Internet'],
                inferred_roles=[''],
                skills=ResumeSkillsPayload(technical=[], tools=[], languages=[]),
            ),
            _build_preferences(all_skipped=True),
        )

        indexed = {item.job_id: item for item in recommendations}
        assert indexed[relevant_job.job_id].base_job_score == 24
        assert indexed[irrelevant_job.job_id].base_job_score == 0
    finally:
        db.close()


def test_recommend_jobs_supports_chinese_profile_and_job_text():
    session_factory = _build_session_factory()
    db = session_factory()
    try:
        chinese_match = _add_job(
            db,
            job_id='job-chinese-match',
            company='甲公司',
            company_type_industry='互联网',
            job_title='后端开发工程师',
            location='上海',
            job_req='熟悉 Python 数据分析 与 后端开发',
            job_duty='负责后端接口与数据处理',
        )
        english_match = _add_job(
            db,
            job_id='job-english-match',
            company='Beta',
            job_title='Operations Analyst',
            location='Beijing',
            job_req='Excel reporting',
            job_duty='Operations support',
        )

        recommendations, _, _ = recommend_jobs_for_profile(
            db,
            _build_profile(
                basic_info={'name': '张三'},
                candidate_summary='有后端开发和数据分析经历',
                inferred_roles=['后端开发'],
                inferred_tracks=['互联网'],
                skills=ResumeSkillsPayload(technical=['Python', '数据分析'], tools=[], languages=[]),
            ),
            _build_preferences(preferred_locations=['上海']),
        )

        assert [item.job_id for item in recommendations[:2]] == [chinese_match.job_id, english_match.job_id]
        assert recommendations[0].objective_score > recommendations[1].objective_score
    finally:
        db.close()


def test_company_tier_tags_contribute_priority_and_enrichment_signals():
    session_factory = _build_session_factory()
    db = session_factory()
    try:
        priority_job = _add_job(
            db,
            job_id='job-priority',
            company='北京抖音信息服务有限公司',
            company_type_industry='互联网',
            job_title='产品经理',
            job_req='负责产品策略',
            job_duty='推动协同落地',
        )
        priority_job.company_tags = '上市, 互联网-一线'
        ordinary_job = _add_job(
            db,
            job_id='job-ordinary',
            company='普通公司',
            company_type_industry='互联网',
            job_title='产品经理',
            job_req='负责产品策略',
            job_duty='推动协同落地',
        )
        db.commit()

        recommendations, _, _ = recommend_jobs_for_profile(
            db,
            _build_profile(inferred_roles=['产品经理'], inferred_tracks=['互联网']),
            _build_preferences(),
            ai_top_n=0,
        )

        indexed = {item.job_id: item for item in recommendations}
        assert indexed[priority_job.job_id].company_priority_label == 'T0-T1 主流平台'
        assert indexed[priority_job.job_id].company_priority_score == 42
        assert indexed[priority_job.job_id].base_match_score > indexed[ordinary_job.job_id].base_match_score
        # Phase 0 (D-4): need_enrichment / topic_cache_status fields removed
        # with the snapshot system. priority + why_recommended remain.
        assert '学生优先赛道：互联网' in indexed[priority_job.job_id].why_recommended
    finally:
        db.close()


def test_state_owned_tier_tags_mark_high_info_asymmetry():
    session_factory = _build_session_factory()
    db = session_factory()
    try:
        job = _add_job(
            db,
            job_id='job-soe',
            company='天翼视联科技有限公司',
            company_type_industry='国央企',
            job_title='管培生',
            job_req='综合培养',
            job_duty='轮岗',
        )
        job.company_tags = '国企, 国央企-第一梯队, 国央企-中国电信'
        db.commit()

        recommendations, _, _ = recommend_jobs_for_profile(
            db,
            _build_profile(inferred_roles=['管培生'], inferred_tracks=['国央企']),
            _build_preferences(),
            ai_top_n=0,
        )

        item = recommendations[0]
        assert item.job_id == job.job_id
        assert item.company_priority_label == 'T0 央企核心平台'
        # Phase 0 (D-4): need_enrichment / enrichment_reason fields removed
        # with the snapshot system. high_info_asymmetry now surfaces only via
        # priority metadata + LLM rerank.
    finally:
        db.close()


def test_company_priority_does_not_match_aliases_from_job_description_only():
    session_factory = _build_session_factory()
    db = session_factory()
    try:
        ordinary_job = _add_job(
            db,
            job_id='job-ordinary',
            company='彩讯科技股份有限公司',
            company_type_industry='互联网',
            job_title='AI运营工程师',
            job_req='负责中国电信客户相关项目推进',
            job_duty='对接运营商客户需求',
        )

        recommendations, _, _ = recommend_jobs_for_profile(
            db,
            _build_profile(inferred_roles=['AI运营工程师'], inferred_tracks=['互联网']),
            _build_preferences(),
            ai_top_n=0,
        )

        item = next(result for result in recommendations if result.job_id == ordinary_job.job_id)
        assert item.company_priority_label == ''
        assert item.company_priority_score == 0
    finally:
        db.close()


class _SuccessfulRecommendationProvider:
    def rerank_recommendations(self, profile, preferences, items, **_kwargs):
        top = list(items)
        top[0] = top[0].model_copy(
            update={
                'final_score': top[0].base_match_score + 9,
                'used_ai': True,
                'why_recommended': ['Strong backend match'],
                'strengths': ['Python'],
                'risks': ['Needs distributed systems depth'],
            }
        )
        return top


class _FailingRecommendationProvider:
    def rerank_recommendations(self, profile, preferences, items, **_kwargs):
        raise RuntimeError('rerank unavailable')


def test_ai_rerank_updates_top_items_when_provider_succeeds():
    session_factory = _build_session_factory()
    db = session_factory()
    try:
        _add_job(db, job_id='job-strong', company='Alpha', job_title='Backend Engineer', job_req='Python APIs')
        _add_job(db, job_id='job-weak', company='Beta', job_title='Analyst', job_req='Excel')

        recommendations, used_ai, fallback_reason = recommend_jobs_for_profile(
            db,
            _build_profile(),
            _build_preferences(),
            ai_provider=_SuccessfulRecommendationProvider(),
            ai_top_n=1,
        )

        assert used_ai is True
        assert fallback_reason == ''
        assert recommendations[0].used_ai is True
        assert recommendations[0].why_recommended == ['Strong backend match']
        assert recommendations[0].strengths == ['Python']
        assert recommendations[0].risks == ['Needs distributed systems depth']
        assert recommendations[0].final_score > recommendations[0].base_match_score
        assert recommendations[1].used_ai is False
    finally:
        db.close()


def test_ai_rerank_failure_falls_back_to_rule_only_recommendations():
    session_factory = _build_session_factory()
    db = session_factory()
    try:
        strongest = _add_job(db, job_id='job-strong', company='Alpha', job_title='Backend Engineer', job_req='Python APIs')
        weaker = _add_job(db, job_id='job-weak', company='Beta', job_title='Analyst', job_req='Excel')

        recommendations, used_ai, fallback_reason = recommend_jobs_for_profile(
            db,
            _build_profile(),
            _build_preferences(),
            ai_provider=_FailingRecommendationProvider(),
            ai_top_n=2,
        )

        assert [item.job_id for item in recommendations[:2]] == [strongest.job_id, weaker.job_id]
        assert used_ai is False
        assert fallback_reason == 'rerank unavailable'
        assert all(item.used_ai is False for item in recommendations)
        assert all(item.final_score == item.base_match_score for item in recommendations)
    finally:
        db.close()
