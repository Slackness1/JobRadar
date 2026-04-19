import json

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import (
    Job,
    ResumeConfirmedProfile,
    ResumeCopilotSession,
    ResumeFeedbackRun,
    ResumePreferenceProfile,
    ResumeRecommendationRun,
)
from app.schemas_resume_copilot import ResumePreferencePayload, ResumeProfilePayload, ResumeSkillsPayload
from app.services.resume_copilot.workflow import run_resume_generate_workflow


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
        'basic_info': {'name': 'Jane Doe', 'email': 'jane@example.com'},
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
        'preferred_tracks': ['Internet'],
        'preferred_locations': ['Shanghai'],
        'preferred_roles': ['Backend Engineer'],
        'preferred_company_types': ['Internet'],
        'accept_relocation': False,
        'accept_internship': False,
        'campus_only': False,
        'social_ok': False,
        'preference_notes': '',
        'all_skipped': False,
    }
    payload.update(overrides)
    return ResumePreferencePayload.model_validate(payload)


def _seed_session(db: Session) -> int:
    session = ResumeCopilotSession(
        file_name='resume.pdf',
        status='awaiting_user_confirmation',
        recommendation_status='running',
        feedback_status='running',
        extracted_text='Jane Doe',
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    profile = _build_profile()
    preferences = _build_preferences()
    db.add(ResumeConfirmedProfile(session_id=session.id, profile_json=json.dumps(profile.model_dump())))
    db.add(ResumePreferenceProfile(session_id=session.id, preferences_json=json.dumps(preferences.model_dump()), all_skipped=0))
    db.commit()
    return int(session.id)


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


class _SuccessfulRecommendationProvider:
    def rerank_recommendations(self, profile, preferences, items):
        reranked = list(items)
        reranked[0] = reranked[0].model_copy(
            update={
                'used_ai': True,
                'final_score': reranked[0].rule_score + 11,
                'why_recommended': ['Matches backend track'],
                'strengths': ['Python', 'SQL'],
                'risks': ['Needs stronger distributed systems exposure'],
            }
        )
        return reranked


class _FailingRecommendationProvider:
    def rerank_recommendations(self, profile, preferences, items):
        raise RuntimeError('rerank provider unavailable')


class _SuccessfulFeedbackProvider:
    def generate_feedback(self, profile, preferences, recommendations):
        return {
            'diagnostics': [
                {
                    'title': 'Clarify distributed systems impact',
                    'description': 'Highlight scale, latency, or throughput outcomes relevant to backend roles.',
                }
            ],
            'rewrite_examples': [
                {
                    'section': 'experience',
                    'original': 'Built APIs',
                    'improved': 'Built Python APIs serving 10k requests per day',
                    'rationale': 'Adds measurable impact for backend hiring managers.',
                }
            ],
        }


class _FailingFeedbackProvider:
    def generate_feedback(self, profile, preferences, recommendations):
        raise RuntimeError('feedback provider unavailable')


def test_generate_workflow_persists_recommendations_and_feedback():
    session_factory = _build_session_factory()
    db = session_factory()
    try:
        session_id = _seed_session(db)
        _add_job(db, job_id='job-strong', company='Alpha', job_title='Backend Engineer', job_req='Python SQL APIs')
        _add_job(db, job_id='job-weak', company='Beta', job_title='Analyst', job_req='Excel reporting')
    finally:
        db.close()

    run_resume_generate_workflow(
        session_id,
        session_factory=session_factory,
        recommendation_provider=_SuccessfulRecommendationProvider(),
        feedback_provider=_SuccessfulFeedbackProvider(),
    )

    db = session_factory()
    try:
        session = db.query(ResumeCopilotSession).filter(ResumeCopilotSession.id == session_id).first()
        recommendation_run = db.query(ResumeRecommendationRun).filter(ResumeRecommendationRun.session_id == session_id).first()
        feedback_run = db.query(ResumeFeedbackRun).filter(ResumeFeedbackRun.session_id == session_id).first()
        assert session is not None
        assert recommendation_run is not None
        assert feedback_run is not None
        assert session.status == 'completed'
        assert session.recommendation_status == 'completed'
        assert session.feedback_status == 'completed'
        assert recommendation_run.status == 'completed'
        assert recommendation_run.used_ai == 1
        assert recommendation_run.fallback_reason == ''
        assert feedback_run.status == 'completed'
        diagnostics = json.loads(feedback_run.diagnostics_json)
        rewrites = json.loads(feedback_run.rewrite_examples_json)
        assert diagnostics[0]['title'] == 'Clarify distributed systems impact'
        assert diagnostics[0]['description'] == 'Highlight scale, latency, or throughput outcomes relevant to backend roles.'
        assert rewrites[0]['section'] == 'experience'
        assert rewrites[0]['original'] == 'Built APIs'
        assert rewrites[0]['improved'] == 'Built Python APIs serving 10k requests per day'
        assert rewrites[0]['rationale'] == 'Adds measurable impact for backend hiring managers.'
    finally:
        db.close()


def test_generate_workflow_falls_back_to_rule_only_when_ai_rerank_fails():
    session_factory = _build_session_factory()
    db = session_factory()
    try:
        session_id = _seed_session(db)
        _add_job(db, job_id='job-strong', company='Alpha', job_title='Backend Engineer', job_req='Python SQL APIs')
        _add_job(db, job_id='job-weak', company='Beta', job_title='Analyst', job_req='Excel reporting')
    finally:
        db.close()

    run_resume_generate_workflow(
        session_id,
        session_factory=session_factory,
        recommendation_provider=_FailingRecommendationProvider(),
        feedback_provider=_SuccessfulFeedbackProvider(),
    )

    db = session_factory()
    try:
        session = db.query(ResumeCopilotSession).filter(ResumeCopilotSession.id == session_id).first()
        recommendation_run = db.query(ResumeRecommendationRun).filter(ResumeRecommendationRun.session_id == session_id).first()
        assert session is not None
        assert recommendation_run is not None
        assert session.status == 'completed'
        assert session.recommendation_status == 'completed'
        assert session.feedback_status == 'completed'
        assert recommendation_run.status == 'completed'
        assert recommendation_run.used_ai == 1
        assert recommendation_run.fallback_reason == ''
        recommendations = json.loads(recommendation_run.recommendations_json)
        assert all(item['used_ai'] is False for item in recommendations)
        assert all(item['final_score'] == item['rule_score'] for item in recommendations)
    finally:
        db.close()


def test_generate_workflow_keeps_recommendations_when_feedback_generation_fails():
    session_factory = _build_session_factory()
    db = session_factory()
    try:
        session_id = _seed_session(db)
        _add_job(db, job_id='job-strong', company='Alpha', job_title='Backend Engineer', job_req='Python SQL APIs')
    finally:
        db.close()

    run_resume_generate_workflow(
        session_id,
        session_factory=session_factory,
        recommendation_provider=_SuccessfulRecommendationProvider(),
        feedback_provider=_FailingFeedbackProvider(),
    )

    db = session_factory()
    try:
        session = db.query(ResumeCopilotSession).filter(ResumeCopilotSession.id == session_id).first()
        recommendation_run = db.query(ResumeRecommendationRun).filter(ResumeRecommendationRun.session_id == session_id).first()
        feedback_run = db.query(ResumeFeedbackRun).filter(ResumeFeedbackRun.session_id == session_id).first()
        assert session is not None
        assert recommendation_run is not None
        assert feedback_run is not None
        assert session.status == 'completed'
        assert session.recommendation_status == 'completed'
        assert session.feedback_status == 'failed'
        assert recommendation_run.status == 'completed'
        assert feedback_run.status == 'failed'
        assert feedback_run.error_message == 'feedback provider unavailable'
    finally:
        db.close()


def test_generate_workflow_feedback_uses_preferences_and_top_recommendations():
    session_factory = _build_session_factory()
    observed = {}
    db = session_factory()
    try:
        session_id = _seed_session(db)
        _add_job(db, job_id='job-strong', company='Alpha', job_title='Backend Engineer', job_req='Python SQL APIs')
    finally:
        db.close()

    class _ObservingFeedbackProvider:
        def generate_feedback(self, profile, preferences, recommendations):
            observed['profile_name'] = profile.basic_info.get('name')
            observed['preferred_locations'] = preferences.preferred_locations if preferences else []
            observed['top_job_id'] = recommendations[0].job_id
            return {
                'diagnostics': [{'title': 'One', 'description': 'Two'}],
                'rewrite_examples': [
                    {
                        'section': 'experience',
                        'original': 'Built APIs',
                        'improved': 'Built APIs used by recruiters',
                        'rationale': 'Makes impact clearer',
                    }
                ],
            }

    run_resume_generate_workflow(
        session_id,
        session_factory=session_factory,
        recommendation_provider=_SuccessfulRecommendationProvider(),
        feedback_provider=_ObservingFeedbackProvider(),
    )

    assert observed == {
        'profile_name': 'Jane Doe',
        'preferred_locations': ['Shanghai'],
        'top_job_id': 'job-strong',
    }
