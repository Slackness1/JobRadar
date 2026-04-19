import json
from urllib.error import HTTPError
from urllib.error import URLError

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app as main_app
from app.models import (
    ResumeConfirmedProfile,
    ResumeCopilotSession,
    ResumeDirectionAnalysisRun,
    ResumeFeedbackRun,
    ResumeParsedProfile,
    ResumePreferenceProfile,
    ResumeRecommendationRun,
)
from app.services.resume_copilot.workflow import run_resume_parse_workflow


def _build_test_client():
    from app.routers import resume_copilot

    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    test_app = FastAPI()
    test_app.include_router(resume_copilot.router)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    test_app.dependency_overrides[get_db] = override_get_db
    return TestClient(test_app), testing_session_local


def _seed_session(db: Session, **overrides) -> ResumeCopilotSession:
    session = ResumeCopilotSession(
        file_name=overrides.get('file_name', 'resume.pdf'),
        status=overrides.get('status', 'uploaded'),
        extracted_text=overrides.get('extracted_text', ''),
        error_message=overrides.get('error_message', ''),
        recommendation_status=overrides.get('recommendation_status', 'pending'),
        feedback_status=overrides.get('feedback_status', 'pending'),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def test_resume_copilot_routes_are_registered_in_main_app():
    route_paths = {getattr(route, 'path', '') for route in main_app.routes}

    assert '/api/resume-copilot/sessions' in route_paths
    assert '/api/resume-copilot/sessions/{session_id}' in route_paths
    assert '/api/resume-copilot/sessions/{session_id}/parsed-profile' in route_paths
    assert '/api/resume-copilot/sessions/{session_id}/confirmed-profile' in route_paths
    assert '/api/resume-copilot/sessions/{session_id}/preferences' in route_paths
    assert '/api/resume-copilot/sessions/{session_id}/generate' in route_paths
    assert '/api/resume-copilot/sessions/{session_id}/recommendations' in route_paths
    assert '/api/resume-copilot/sessions/{session_id}/direction-analysis' in route_paths


def test_create_session_rejects_non_pdf_upload():
    client, _ = _build_test_client()

    response = client.post(
        '/api/resume-copilot/sessions',
        files={'file': ('resume.txt', b'hello', 'text/plain')},
    )

    assert response.status_code == 400
    assert response.json() == {'detail': 'INVALID_FILE_TYPE'}


def test_create_session_stores_extracted_text_for_valid_pdf(monkeypatch):
    client, testing_session_local = _build_test_client()
    observed = {}

    monkeypatch.setattr(
        'app.routers.resume_copilot.extract_resume_text_from_pdf',
        lambda _file_bytes: 'Jane Doe\n\nPython, SQL',
    )
    monkeypatch.setattr(
        'app.routers.resume_copilot.run_resume_parse_workflow',
        lambda session_id: observed.setdefault('session_id', session_id),
    )

    response = client.post(
        '/api/resume-copilot/sessions',
        files={'file': ('resume.pdf', b'%PDF-1.4\ncontent', 'application/pdf')},
    )

    assert response.status_code == 202
    assert response.json() == {'session_id': 1, 'status': 'parsing_profile'}
    assert observed == {'session_id': 1}

    db = testing_session_local()
    try:
        session = db.query(ResumeCopilotSession).filter(ResumeCopilotSession.id == 1).first()
        assert session is not None
        assert session.status == 'parsing_profile'
        assert session.extracted_text == 'Jane Doe\n\nPython, SQL'
    finally:
        db.close()


class _SuccessfulResumeParserProvider:
    def parse_resume_text(self, _resume_text: str):
        return {
            'basic_info': {'name': 'Jane Doe'},
            'education': [],
            'internships': [],
            'projects': [],
            'skills': {'technical': ['Python'], 'tools': [], 'languages': []},
            'languages': ['English'],
            'awards': [],
            'candidate_summary': 'Builder',
            'inferred_roles': ['Backend Engineer'],
            'inferred_tracks': ['Internet'],
        }


class _FailingResumeParserProvider:
    def parse_resume_text(self, _resume_text: str):
        raise ValueError('provider parse failed')


class _RateLimitedResumeParserProvider:
    def parse_resume_text(self, _resume_text: str):
        raise HTTPError(
            url='https://open.bigmodel.cn/api/paas/v4/chat/completions',
            code=429,
            msg='Too Many Requests',
            hdrs=None,
            fp=None,
        )


class _BadRequestResumeParserProvider:
    def parse_resume_text(self, _resume_text: str):
        raise HTTPError(
            url='https://open.bigmodel.cn/api/paas/v4/chat/completions',
            code=400,
            msg='Bad Request',
            hdrs=None,
            fp=None,
        )


class _TimeoutResumeParserProvider:
    def parse_resume_text(self, _resume_text: str):
        raise URLError(TimeoutError('timed out'))


class _MissingApiKeyResumeParserProvider:
    def parse_resume_text(self, _resume_text: str):
        raise ValueError('RESUME_COPILOT_LLM_API_KEY is not configured')


def test_run_resume_parse_workflow_persists_profile_and_updates_session_status():
    _, testing_session_local = _build_test_client()

    db = testing_session_local()
    try:
        seeded = _seed_session(db, status='parsing_profile', extracted_text='Jane Doe\nPython')
        seeded_id = seeded.id
    finally:
        db.close()

    run_resume_parse_workflow(seeded_id, session_factory=testing_session_local, provider=_SuccessfulResumeParserProvider())

    db = testing_session_local()
    try:
        session = db.query(ResumeCopilotSession).filter(ResumeCopilotSession.id == seeded_id).first()
        profile = db.query(ResumeParsedProfile).filter(ResumeParsedProfile.session_id == seeded_id).first()
        assert session is not None
        assert profile is not None
        assert session.status == 'awaiting_user_confirmation'
        assert session.error_message == ''
        stored_profile = json.loads(profile.profile_json)
        assert stored_profile['basic_info']['name'] == 'Jane Doe'
        assert stored_profile['skills']['technical'] == ['Python']
    finally:
        db.close()


def test_run_resume_parse_workflow_marks_session_failed_on_parser_error():
    _, testing_session_local = _build_test_client()

    db = testing_session_local()
    try:
        seeded = _seed_session(db, status='parsing_profile', extracted_text='Jane Doe\nPython')
        seeded_id = seeded.id
    finally:
        db.close()

    run_resume_parse_workflow(seeded_id, session_factory=testing_session_local, provider=_FailingResumeParserProvider())

    db = testing_session_local()
    try:
        session = db.query(ResumeCopilotSession).filter(ResumeCopilotSession.id == seeded_id).first()
        profile = db.query(ResumeParsedProfile).filter(ResumeParsedProfile.session_id == seeded_id).first()
        assert session is not None
        assert profile is None
        assert session.status == 'failed'
        assert session.error_message == 'provider parse failed'
    finally:
        db.close()


def test_run_resume_parse_workflow_clears_stale_profile_when_rerun_fails():
    _, testing_session_local = _build_test_client()

    db = testing_session_local()
    try:
        seeded = _seed_session(db, status='parsing_profile', extracted_text='Jane Doe\nPython')
        seeded_id = seeded.id
        db.add(ResumeParsedProfile(session_id=seeded_id, profile_json='{"basic_info":{"name":"Old"}}'))
        db.commit()
    finally:
        db.close()


def test_run_resume_parse_workflow_falls_back_to_heuristic_profile_on_rate_limit():
    _, testing_session_local = _build_test_client()

    db = testing_session_local()
    try:
        seeded = _seed_session(
            db,
            status='parsing_profile',
            extracted_text='Jane Doe\njane@example.com\nPython SQL React\nBackend Engineer Intern',
        )
        seeded_id = seeded.id
    finally:
        db.close()

    run_resume_parse_workflow(seeded_id, session_factory=testing_session_local, provider=_RateLimitedResumeParserProvider())

    db = testing_session_local()
    try:
        session = db.query(ResumeCopilotSession).filter(ResumeCopilotSession.id == seeded_id).first()
        profile = db.query(ResumeParsedProfile).filter(ResumeParsedProfile.session_id == seeded_id).first()
        assert session is not None
        assert profile is not None
        assert session.status == 'awaiting_user_confirmation'
        assert session.error_message == ''
        stored_profile = json.loads(profile.profile_json)
        assert stored_profile['basic_info']['name'] == 'Jane Doe'
        assert stored_profile['basic_info']['email'] == 'jane@example.com'
        assert 'Python' in stored_profile['skills']['technical']
    finally:
        db.close()


def test_run_resume_parse_workflow_falls_back_to_heuristic_profile_on_upstream_bad_request():
    _, testing_session_local = _build_test_client()

    db = testing_session_local()
    try:
        seeded = _seed_session(
            db,
            status='parsing_profile',
            extracted_text='Jane Doe\njane@example.com\nPython SQL React\nBackend Engineer Intern',
        )
        seeded_id = seeded.id
    finally:
        db.close()

    run_resume_parse_workflow(seeded_id, session_factory=testing_session_local, provider=_BadRequestResumeParserProvider())

    db = testing_session_local()
    try:
        session = db.query(ResumeCopilotSession).filter(ResumeCopilotSession.id == seeded_id).first()
        profile = db.query(ResumeParsedProfile).filter(ResumeParsedProfile.session_id == seeded_id).first()
        assert session is not None
        assert profile is not None
        assert session.status == 'awaiting_user_confirmation'
        assert session.error_message == ''
        stored_profile = json.loads(profile.profile_json)
        assert stored_profile['basic_info']['name'] == 'Jane Doe'
        assert stored_profile['basic_info']['email'] == 'jane@example.com'
        assert 'Python' in stored_profile['skills']['technical']
    finally:
        db.close()


def test_run_resume_parse_workflow_falls_back_to_heuristic_profile_on_upstream_timeout():
    _, testing_session_local = _build_test_client()

    db = testing_session_local()
    try:
        seeded = _seed_session(
            db,
            status='parsing_profile',
            extracted_text='Jane Doe\njane@example.com\nPython SQL React\nBackend Engineer Intern',
        )
        seeded_id = seeded.id
    finally:
        db.close()


def test_run_resume_parse_workflow_falls_back_to_heuristic_profile_when_api_key_missing():
    _, testing_session_local = _build_test_client()

    db = testing_session_local()
    try:
        seeded = _seed_session(
            db,
            status='parsing_profile',
            extracted_text='Jane Doe\njane@example.com\nPython SQL React\nBackend Engineer Intern',
        )
        seeded_id = seeded.id
    finally:
        db.close()

    run_resume_parse_workflow(seeded_id, session_factory=testing_session_local, provider=_MissingApiKeyResumeParserProvider())

    db = testing_session_local()
    try:
        session = db.query(ResumeCopilotSession).filter(ResumeCopilotSession.id == seeded_id).first()
        profile = db.query(ResumeParsedProfile).filter(ResumeParsedProfile.session_id == seeded_id).first()
        assert session is not None
        assert profile is not None
        assert session.status == 'awaiting_user_confirmation'
        assert session.error_message == ''
        stored_profile = json.loads(profile.profile_json)
        assert stored_profile['basic_info']['name'] == 'Jane Doe'
        assert stored_profile['basic_info']['email'] == 'jane@example.com'
        assert 'Python' in stored_profile['skills']['technical']
    finally:
        db.close()

    run_resume_parse_workflow(seeded_id, session_factory=testing_session_local, provider=_TimeoutResumeParserProvider())

    db = testing_session_local()
    try:
        session = db.query(ResumeCopilotSession).filter(ResumeCopilotSession.id == seeded_id).first()
        profile = db.query(ResumeParsedProfile).filter(ResumeParsedProfile.session_id == seeded_id).first()
        assert session is not None
        assert profile is not None
        assert session.status == 'awaiting_user_confirmation'
        assert session.error_message == ''
        stored_profile = json.loads(profile.profile_json)
        assert stored_profile['basic_info']['name'] == 'Jane Doe'
        assert stored_profile['basic_info']['email'] == 'jane@example.com'
        assert 'Python' in stored_profile['skills']['technical']
    finally:
        db.close()

    run_resume_parse_workflow(seeded_id, session_factory=testing_session_local, provider=_FailingResumeParserProvider())

    db = testing_session_local()
    try:
        session = db.query(ResumeCopilotSession).filter(ResumeCopilotSession.id == seeded_id).first()
        profile = db.query(ResumeParsedProfile).filter(ResumeParsedProfile.session_id == seeded_id).first()
        assert session is not None
        assert profile is None
        assert session.status == 'failed'
        assert session.error_message == 'provider parse failed'
    finally:
        db.close()


def test_get_session_returns_404_for_unknown_id():
    client, _ = _build_test_client()

    response = client.get('/api/resume-copilot/sessions/999')

    assert response.status_code == 404
    assert response.json() == {'detail': 'Resume copilot session 999 not found'}


def test_get_parsed_profile_returns_404_when_profile_missing():
    client, testing_session_local = _build_test_client()

    db = testing_session_local()
    try:
        seeded = _seed_session(db)
    finally:
        db.close()

    response = client.get(f'/api/resume-copilot/sessions/{seeded.id}/parsed-profile')

    assert response.status_code == 404
    assert response.json() == {'detail': f'Parsed profile for session {seeded.id} not found'}


def test_get_confirmed_profile_returns_404_when_missing():
    client, testing_session_local = _build_test_client()

    db = testing_session_local()
    try:
        seeded = _seed_session(db)
    finally:
        db.close()

    response = client.get(f'/api/resume-copilot/sessions/{seeded.id}/confirmed-profile')

    assert response.status_code == 404
    assert response.json() == {'detail': f'Confirmed profile for session {seeded.id} not found'}


def test_put_confirmed_profile_upserts_profile_json():
    client, testing_session_local = _build_test_client()

    db = testing_session_local()
    try:
        seeded = _seed_session(db)
        seeded_id = seeded.id
    finally:
        db.close()

    payload = {
        'profile': {
            'basic_info': {'name': 'Jane Doe', 'email': 'jane@example.com'},
            'education': [],
            'internships': [],
            'projects': [],
            'skills': {'technical': ['Python'], 'tools': ['Git'], 'languages': []},
            'languages': ['English'],
            'awards': [],
            'candidate_summary': 'Backend focused candidate',
            'inferred_roles': ['Backend Engineer'],
            'inferred_tracks': ['Internet'],
        }
    }

    first_response = client.put(f'/api/resume-copilot/sessions/{seeded_id}/confirmed-profile', json=payload)
    second_payload = {
        'profile': {
            **payload['profile'],
            'candidate_summary': 'Updated summary',
            'inferred_roles': ['Platform Engineer'],
        }
    }
    second_response = client.put(f'/api/resume-copilot/sessions/{seeded_id}/confirmed-profile', json=second_payload)
    get_response = client.get(f'/api/resume-copilot/sessions/{seeded_id}/confirmed-profile')

    assert first_response.status_code == 200
    assert first_response.json() == {'session_id': seeded_id, 'profile': payload['profile']}
    assert second_response.status_code == 200
    assert second_response.json() == {'session_id': seeded_id, 'profile': second_payload['profile']}
    assert get_response.status_code == 200
    assert get_response.json() == {'session_id': seeded_id, 'profile': second_payload['profile']}

    db = testing_session_local()
    try:
        confirmed_profile = (
            db.query(ResumeConfirmedProfile)
            .filter(ResumeConfirmedProfile.session_id == seeded_id)
            .first()
        )
        assert confirmed_profile is not None
        assert json.loads(confirmed_profile.profile_json) == second_payload['profile']
    finally:
        db.close()


def test_get_preferences_returns_404_when_missing():
    client, testing_session_local = _build_test_client()

    db = testing_session_local()
    try:
        seeded = _seed_session(db)
    finally:
        db.close()

    response = client.get(f'/api/resume-copilot/sessions/{seeded.id}/preferences')

    assert response.status_code == 404
    assert response.json() == {'detail': f'Preferences for session {seeded.id} not found'}


def test_put_preferences_upserts_preferences_json_and_all_skipped():
    client, testing_session_local = _build_test_client()

    db = testing_session_local()
    try:
        seeded = _seed_session(db)
        seeded_id = seeded.id
    finally:
        db.close()

    payload = {
        'preferences': {
            'preferred_tracks': ['Internet', 'Banking'],
            'preferred_locations': ['Shanghai'],
            'preferred_roles': ['Backend Engineer'],
            'preferred_company_types': ['State-owned'],
            'accept_relocation': True,
            'accept_internship': False,
            'campus_only': True,
            'social_ok': False,
            'preference_notes': 'Prefer data-heavy teams',
            'all_skipped': False,
        }
    }
    skipped_payload = {
        'preferences': {
            'preferred_tracks': [],
            'preferred_locations': [],
            'preferred_roles': [],
            'preferred_company_types': [],
            'accept_relocation': False,
            'accept_internship': False,
            'campus_only': False,
            'social_ok': False,
            'preference_notes': '',
            'all_skipped': True,
        }
    }

    first_response = client.put(f'/api/resume-copilot/sessions/{seeded_id}/preferences', json=payload)
    second_response = client.put(f'/api/resume-copilot/sessions/{seeded_id}/preferences', json=skipped_payload)
    get_response = client.get(f'/api/resume-copilot/sessions/{seeded_id}/preferences')

    assert first_response.status_code == 200
    assert first_response.json() == {'session_id': seeded_id, 'preferences': payload['preferences']}
    assert second_response.status_code == 200
    assert second_response.json() == {'session_id': seeded_id, 'preferences': skipped_payload['preferences']}
    assert get_response.status_code == 200
    assert get_response.json() == {'session_id': seeded_id, 'preferences': skipped_payload['preferences']}

    db = testing_session_local()
    try:
        preference_profile = (
            db.query(ResumePreferenceProfile)
            .filter(ResumePreferenceProfile.session_id == seeded_id)
            .first()
        )
        assert preference_profile is not None
        assert json.loads(preference_profile.preferences_json) == skipped_payload['preferences']
        assert preference_profile.all_skipped == 1
    finally:
        db.close()


def test_generate_returns_409_without_confirmed_profile():
    client, testing_session_local = _build_test_client()

    db = testing_session_local()
    try:
        seeded = _seed_session(db)
    finally:
        db.close()

    response = client.post(f'/api/resume-copilot/sessions/{seeded.id}/generate')

    assert response.status_code == 409
    assert response.json() == {'detail': 'CONFIRMED_PROFILE_REQUIRED'}


def test_generate_sets_running_statuses_and_queues_background_work_when_confirmed_profile_exists(monkeypatch):
    client, testing_session_local = _build_test_client()
    observed = {}

    monkeypatch.setattr(
        'app.routers.resume_copilot.run_resume_generate_workflow',
        lambda session_id: observed.setdefault('session_id', session_id),
    )

    db = testing_session_local()
    try:
        seeded = _seed_session(db)
        seeded_id = seeded.id
        db.add(ResumeConfirmedProfile(session_id=seeded_id, profile_json='{}'))
        db.commit()
    finally:
        db.close()

    response = client.post(f'/api/resume-copilot/sessions/{seeded_id}/generate')

    assert response.status_code == 202
    assert response.json() == {'session_id': seeded_id, 'status': 'running'}
    assert observed == {'session_id': seeded_id}

    db = testing_session_local()
    try:
        session = db.query(ResumeCopilotSession).filter(ResumeCopilotSession.id == seeded_id).first()
        recommendation_run = (
            db.query(ResumeRecommendationRun)
            .filter(ResumeRecommendationRun.session_id == seeded_id)
            .first()
        )
        direction_run = db.query(ResumeDirectionAnalysisRun).filter(ResumeDirectionAnalysisRun.session_id == seeded_id).first()
        assert session is not None
        assert recommendation_run is not None
        assert direction_run is not None
        assert session.recommendation_status == 'running'
        assert session.feedback_status == 'running'
        assert recommendation_run.status == 'running'
        assert direction_run.status == 'running'
    finally:
        db.close()


def test_generate_clears_stale_recommendation_and_feedback_payloads_before_rerun(monkeypatch):
    client, testing_session_local = _build_test_client()
    observed = {}

    monkeypatch.setattr(
        'app.routers.resume_copilot.run_resume_generate_workflow',
        lambda session_id: observed.setdefault('session_id', session_id),
    )

    db = testing_session_local()
    try:
        seeded = _seed_session(db, recommendation_status='completed', feedback_status='completed')
        seeded_id = seeded.id
        db.add(ResumeConfirmedProfile(session_id=seeded_id, profile_json='{}'))
        db.add(
            ResumeRecommendationRun(
                session_id=seeded_id,
                status='completed',
                used_ai=1,
                fallback_reason='old fallback',
                recommendations_json='[{"job_id":"old"}]',
            )
        )
        db.add(
            ResumeDirectionAnalysisRun(
                session_id=seeded_id,
                status='completed',
                directions_json='[{"direction":"old"}]',
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.post(f'/api/resume-copilot/sessions/{seeded_id}/generate')

    assert response.status_code == 202
    assert observed == {'session_id': seeded_id}

    db = testing_session_local()
    try:
        recommendation_run = db.query(ResumeRecommendationRun).filter(ResumeRecommendationRun.session_id == seeded_id).first()
        direction_run = db.query(ResumeDirectionAnalysisRun).filter(ResumeDirectionAnalysisRun.session_id == seeded_id).first()
        assert recommendation_run is not None
        assert direction_run is not None
        assert recommendation_run.status == 'running'
        assert recommendation_run.used_ai == 0
        assert recommendation_run.fallback_reason == ''
        assert recommendation_run.agent_trace_json == '[]'
        assert recommendation_run.recommendations_json == '[]'
        assert direction_run.status == 'running'
        assert direction_run.directions_json == '[]'
    finally:
        db.close()


def test_generate_returns_404_for_unknown_session():
    client, _ = _build_test_client()

    response = client.post('/api/resume-copilot/sessions/999/generate', json={})

    assert response.status_code == 404
    assert response.json() == {'detail': 'Resume copilot session 999 not found'}


def test_get_recommendations_returns_persisted_result():
    client, testing_session_local = _build_test_client()

    db = testing_session_local()
    try:
        seeded = _seed_session(db, recommendation_status='completed')
        seeded_id = seeded.id
        db.add(
            ResumeRecommendationRun(
                session_id=seeded_id,
                status='completed',
                used_ai=1,
                fallback_reason='',
                recommendations_json=json.dumps(
                    [
                        {
                            'job_id': 'job-1',
                            'company': 'Alpha',
                            'job_title': 'Backend Engineer',
                            'location': 'Shanghai',
                            'detail_url': '',
                            'objective_score': 12,
                            'preference_score': 6,
                            'base_job_score': 40,
                            'rule_score': 58,
                            'final_score': 67,
                            'used_ai': True,
                            'why_recommended': ['Strong backend fit'],
                            'strengths': ['Python'],
                            'risks': ['Distributed systems depth'],
                        }
                    ]
                ),
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.get(f'/api/resume-copilot/sessions/{seeded_id}/recommendations')

    assert response.status_code == 200
    assert response.json() == {
        'session_id': seeded_id,
        'status': 'completed',
        'agent_trace': [],
        'used_ai': True,
        'fallback_reason': '',
        'error_message': '',
        'items': [
            {
                'job_id': 'job-1',
                'company': 'Alpha',
                'job_title': 'Backend Engineer',
                'location': 'Shanghai',
                'detail_url': '',
                'objective_score': 12,
                'preference_score': 6,
                'base_job_score': 40,
                'company_priority_score': 0,
                'base_match_score': 0,
                'enhanced_score': 0,
                'rule_score': 58,
                'final_score': 67,
                'matched_track_key': '',
                'matched_track_label': '',
                'matched_role_family': '',
                'company_priority_tier': '',
                'company_priority_label': '',
                'need_enrichment': False,
                'enrichment_reason': '',
                'topic_key': '',
                'topic_cache_status': 'not_needed',
                'topic_summary': '',
                'quick_enrichment_profile': {
                    'summary': '',
                    'likely_orientation': '',
                    'likely_department': '',
                    'target_track_fit': '',
                    'uncertainty_points': [],
                    'search_queries': [],
                    'sources': [],
                },
                'used_ai': True,
                'why_recommended': ['Strong backend fit'],
                'strengths': ['Python'],
                'risks': ['Distributed systems depth'],
                'target_direction': '',
            }
        ],
    }


def test_get_direction_analysis_returns_empty_when_no_run():
    client, testing_session_local = _build_test_client()

    db = testing_session_local()
    try:
        seeded = _seed_session(db)
    finally:
        db.close()

    response = client.get(f'/api/resume-copilot/sessions/{seeded.id}/direction-analysis')

    assert response.status_code == 200
    assert response.json() == []


def test_get_direction_analysis_returns_empty_when_run_not_completed():
    client, testing_session_local = _build_test_client()

    db = testing_session_local()
    try:
        seeded = _seed_session(db)
        seeded_id = seeded.id
        db.add(ResumeDirectionAnalysisRun(session_id=seeded_id, status='running', directions_json='[]'))
        db.commit()
    finally:
        db.close()

    response = client.get(f'/api/resume-copilot/sessions/{seeded_id}/direction-analysis')

    assert response.status_code == 200
    assert response.json() == []


def test_get_direction_analysis_returns_persisted_result():
    client, testing_session_local = _build_test_client()

    db = testing_session_local()
    try:
        seeded = _seed_session(db)
        seeded_id = seeded.id
        db.add(
            ResumeDirectionAnalysisRun(
                session_id=seeded_id,
                status='completed',
                directions_json=json.dumps([
                    {
                        'direction': 'Internet',
                        'tier': 1,
                        'tier_label': '强匹配',
                        'strengths': ['Python', 'Distributed systems'],
                        'gaps': [],
                        'transferable_from': [],
                    }
                ]),
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.get(f'/api/resume-copilot/sessions/{seeded_id}/direction-analysis')

    assert response.status_code == 200
    result = response.json()
    assert len(result) == 1
    assert result[0]['direction'] == 'Internet'
    assert result[0]['tier'] == 1
    assert result[0]['tier_label'] == '强匹配'
    assert 'Python' in result[0]['strengths']
