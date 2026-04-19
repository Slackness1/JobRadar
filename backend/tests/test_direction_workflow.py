import json
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import (
    Job,
    ResumeConfirmedProfile,
    ResumeCopilotSession,
    ResumeDirectionAnalysisRun,
    ResumeCopilotMessage,
    ResumePreferenceProfile,
    ResumeRecommendationRun,
)
from app.schemas_resume_copilot import (
    DirectionTierResult,
    ResumePreferencePayload,
    ResumeProfilePayload,
    ResumeSkillsPayload,
)
from app.services.resume_copilot.workflow import run_resume_generate_workflow


def _build_session_factory():
    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _build_profile():
    return ResumeProfilePayload(
        basic_info={'name': 'Jane Doe'},
        education=[],
        internships=[],
        projects=[],
        skills=ResumeSkillsPayload(technical=['Python'], tools=[], languages=[]),
        languages=[],
        awards=[],
        candidate_summary='Backend-focused',
        inferred_roles=['Backend Engineer'],
        inferred_tracks=['Internet'],
    )


def _build_preferences():
    return ResumePreferencePayload(
        preferred_roles=['Backend Engineer'],
        preferred_tracks=['Internet'],
        preferred_locations=['Shanghai'],
        preferred_company_types=['Internet'],
        accept_relocation=False,
        accept_internship=False,
        campus_only=False,
        social_ok=False,
        preference_notes='',
        all_skipped=False,
    )


def _seed(db: Session) -> int:
    session = ResumeCopilotSession(
        file_name='cv.pdf',
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
    db.add(Job(
        job_id='job-1',
        company='Acme',
        company_type_industry='Internet',
        department='Engineering',
        job_title='Backend Engineer',
        location='Shanghai',
        major_req='CS',
        job_req='Python REST APIs',
        job_duty='Build APIs',
        job_stage='campus',
    ))
    db.commit()
    return int(session.id)


class _StubDirectionProvider:
    def analyze_directions(self, profile, preferences, directions):
        return [
            {
                'direction': d,
                'tier': 1,
                'tier_label': '强匹配',
                'strengths': ['Python'],
                'gaps': [],
                'transferable_from': [],
            }
            for d in directions
        ]


class _StubRecommendationProvider:
    def rerank_recommendations(self, profile, preferences, items):
        return items


def test_workflow_creates_direction_analysis_run():
    factory = _build_session_factory()
    db = factory()
    session_id = _seed(db)
    db.close()

    run_resume_generate_workflow(
        session_id,
        session_factory=factory,
        direction_provider=_StubDirectionProvider(),
        recommendation_provider=_StubRecommendationProvider(),
    )

    db = factory()
    direction_run = db.query(ResumeDirectionAnalysisRun).filter(
        ResumeDirectionAnalysisRun.session_id == session_id
    ).first()
    assert direction_run is not None
    assert direction_run.status == 'completed'
    directions = json.loads(direction_run.directions_json)
    assert isinstance(directions, list)
    db.close()


def test_workflow_creates_initial_chat_message():
    factory = _build_session_factory()
    db = factory()
    session_id = _seed(db)
    db.close()

    run_resume_generate_workflow(
        session_id,
        session_factory=factory,
        direction_provider=_StubDirectionProvider(),
        recommendation_provider=_StubRecommendationProvider(),
    )

    db = factory()
    msgs = db.query(ResumeCopilotMessage).filter(
        ResumeCopilotMessage.session_id == session_id
    ).order_by(ResumeCopilotMessage.created_at).all()
    assert len(msgs) >= 1
    assert msgs[0].role == 'system'
    assert len(msgs[0].content) > 0
    db.close()


def test_workflow_feedback_status_completed():
    factory = _build_session_factory()
    db = factory()
    session_id = _seed(db)
    db.close()

    run_resume_generate_workflow(
        session_id,
        session_factory=factory,
        direction_provider=_StubDirectionProvider(),
        recommendation_provider=_StubRecommendationProvider(),
    )

    db = factory()
    session = db.query(ResumeCopilotSession).filter(
        ResumeCopilotSession.id == session_id
    ).first()
    assert session.feedback_status == 'completed'
    assert session.status == 'completed'
    db.close()
