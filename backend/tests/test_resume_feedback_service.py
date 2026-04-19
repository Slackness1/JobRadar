import json

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import (
    Job,
    ResumeConfirmedProfile,
    ResumeCopilotSession,
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
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _build_profile(**overrides):
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


def _build_preferences(**overrides):
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
    db.add(ResumeConfirmedProfile(
        session_id=session.id,
        profile_json=json.dumps(profile.model_dump()),
    ))
    db.add(ResumePreferenceProfile(
        session_id=session.id,
        preferences_json=json.dumps(preferences.model_dump()),
        all_skipped=0,
    ))
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


class _PassthroughRecommendationProvider:
    def rerank_recommendations(self, profile, preferences, items):
        return items


class _StubDirectionProvider:
    def analyze_directions(self, profile, preferences, directions):
        return [{'direction': d, 'tier': 1, 'tier_label': '强匹配',
                 'strengths': [], 'gaps': [], 'transferable_from': []}
                for d in directions]


def test_generate_workflow_falls_back_to_rule_only_when_ai_rerank_fails():
    class _FailingRecommendationProvider:
        def rerank_recommendations(self, profile, preferences, items):
            raise RuntimeError('rerank provider unavailable')

    session_factory = _build_session_factory()
    db = session_factory()
    try:
        session_id = _seed_session(db)
        _add_job(db, job_id='job-strong', company='Alpha',
                 job_title='Backend Engineer', job_req='Python SQL APIs')
        _add_job(db, job_id='job-weak', company='Beta',
                 job_title='Analyst', job_req='Excel reporting')
    finally:
        db.close()

    run_resume_generate_workflow(
        session_id,
        session_factory=session_factory,
        recommendation_provider=_FailingRecommendationProvider(),
        direction_provider=_StubDirectionProvider(),
    )

    db = session_factory()
    try:
        session = db.query(ResumeCopilotSession).filter(
            ResumeCopilotSession.id == session_id
        ).first()
        recommendation_run = db.query(ResumeRecommendationRun).filter(
            ResumeRecommendationRun.session_id == session_id
        ).first()
        assert session is not None
        assert recommendation_run is not None
        assert session.status == 'completed'
        assert session.recommendation_status == 'completed'
        assert recommendation_run.status == 'completed'
        assert recommendation_run.used_ai == 1
        recommendations = json.loads(recommendation_run.recommendations_json)
        assert all(item['used_ai'] is False for item in recommendations)
    finally:
        db.close()
