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
    ResumeCopilotMessage,
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
    client = TestClient(test_app)
    client.headers.update({'X-Resume-User-Key': 'test-user-key'})
    return client, testing_session_local


def _seed_session(db: Session, **overrides) -> ResumeCopilotSession:
    session = ResumeCopilotSession(
        file_name=overrides.get('file_name', 'resume.pdf'),
        user_key=overrides.get('user_key', 'test-user-key'),
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
        'app.routers.resume_copilot.extract_resume_text_with_page_count',
        lambda _file_bytes: ('Jane Doe\n\nPython, SQL', 2),
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
    body = response.json()
    assert body['session_id'] == 1
    assert body['status'] == 'parsing_profile'
    assert body['page_count'] == 2
    assert body['file_size_bytes'] == len(b'%PDF-1.4\ncontent')
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
                'final_score': 67,
                'matched_track_key': '',
                'matched_track_label': '',
                'matched_role_family': '',
                'company_priority_tier': '',
                'company_priority_label': '',
                'topic_key': '',
                'used_ai': True,
                'why_recommended': ['Strong backend fit'],
                'strengths': ['Python'],
                'risks': ['Distributed systems depth'],
                'target_direction': '',
                'tier_label': '',
                'priority_letter': '',
                'track_match_kind': '',
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


def test_get_chat_messages_returns_empty_for_new_session():
    client, testing_session_local = _build_test_client()

    db = testing_session_local()
    try:
        seeded = _seed_session(db)
    finally:
        db.close()

    response = client.get(f'/api/resume-copilot/sessions/{seeded.id}/chat')

    assert response.status_code == 200
    assert response.json() == []


def test_post_chat_returns_409_when_analysis_not_ready():
    client, testing_session_local = _build_test_client()

    db = testing_session_local()
    try:
        seeded = _seed_session(db)
    finally:
        db.close()

    response = client.post(
        f'/api/resume-copilot/sessions/{seeded.id}/chat',
        json={'content': 'Hello'},
    )

    assert response.status_code == 409
    assert response.json() == {'detail': 'DIRECTION_ANALYSIS_NOT_READY'}


def test_post_apply_rewrite_returns_422_on_bad_path():
    client, testing_session_local = _build_test_client()

    db = testing_session_local()
    try:
        seeded = _seed_session(db)
        seeded_id = seeded.id
        db.add(ResumeConfirmedProfile(
            session_id=seeded_id,
            profile_json=json.dumps({
                'basic_info': {'name': 'Jane', 'email': ''},
                'education': [], 'internships': [], 'projects': [],
                'skills': {'technical': [], 'tools': [], 'languages': []},
                'languages': [], 'awards': [],
                'candidate_summary': '', 'inferred_roles': [], 'inferred_tracks': [],
            }),
        ))
        msg = ResumeCopilotMessage(
            session_id=seeded_id,
            role='assistant',
            content='Here are your options',
            rewrite_options_json=json.dumps([{
                'option_id': 'A',
                'label': 'Option A',
                'section': 'internships',
                'field_path': 'internships.99.bullets.0',
                'original': 'old text',
                'improved': 'new text',
                'rationale': 'Better',
            }]),
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        msg_id = msg.id
    finally:
        db.close()

    response = client.post(
        f'/api/resume-copilot/sessions/{seeded_id}/chat/apply-rewrite',
        json={'message_id': msg_id, 'option_id': 'A'},
    )

    assert response.status_code == 422


def test_get_chat_messages_returns_persisted_messages():
    client, testing_session_local = _build_test_client()

    db = testing_session_local()
    try:
        seeded = _seed_session(db)
        seeded_id = seeded.id
        db.add(ResumeCopilotMessage(
            session_id=seeded_id,
            role='system',
            content='Welcome to the chat!',
        ))
        db.commit()
    finally:
        db.close()

    response = client.get(f'/api/resume-copilot/sessions/{seeded_id}/chat')

    assert response.status_code == 200
    result = response.json()
    assert len(result) == 1
    assert result[0]['role'] == 'system'
    assert result[0]['content'] == 'Welcome to the chat!'
    assert result[0]['rewrite_options'] is None
    assert result[0]['applied_option_id'] is None


# ─── C1: session ownership / auth ────────────────────────────────────────────


def test_get_session_rejects_mismatched_user_key():
    client, testing_session_local = _build_test_client()

    db = testing_session_local()
    try:
        seeded = _seed_session(db, user_key='owner-A')
        seeded_id = seeded.id
    finally:
        db.close()

    # Default test header is 'test-user-key', not 'owner-A' → should 403
    response = client.get(f'/api/resume-copilot/sessions/{seeded_id}')
    assert response.status_code == 403
    assert response.json() == {'detail': 'SESSION_FORBIDDEN'}


def test_get_session_rejects_empty_user_key_header():
    client, testing_session_local = _build_test_client()

    db = testing_session_local()
    try:
        seeded = _seed_session(db, user_key='owner-A')
        seeded_id = seeded.id
    finally:
        db.close()

    response = client.get(
        f'/api/resume-copilot/sessions/{seeded_id}',
        headers={'X-Resume-User-Key': ''},
    )
    assert response.status_code == 403


def test_owner_can_access_their_own_session():
    client, testing_session_local = _build_test_client()

    db = testing_session_local()
    try:
        seeded = _seed_session(db, user_key='owner-A')
        seeded_id = seeded.id
    finally:
        db.close()

    response = client.get(
        f'/api/resume-copilot/sessions/{seeded_id}',
        headers={'X-Resume-User-Key': 'owner-A'},
    )
    assert response.status_code == 200
    assert response.json()['id'] == seeded_id


def test_demo_session_is_publicly_readable():
    client, testing_session_local = _build_test_client()

    db = testing_session_local()
    try:
        seeded = _seed_session(db, user_key='__demo__')
        seeded_id = seeded.id
    finally:
        db.close()

    # Strangers can read demo session — no key, mismatched key, etc.
    no_key = client.get(
        f'/api/resume-copilot/sessions/{seeded_id}',
        headers={'X-Resume-User-Key': ''},
    )
    stranger = client.get(
        f'/api/resume-copilot/sessions/{seeded_id}',
        headers={'X-Resume-User-Key': 'stranger-Z'},
    )
    assert no_key.status_code == 200
    assert stranger.status_code == 200


def test_demo_session_blocks_writes_even_for_strangers():
    client, testing_session_local = _build_test_client()

    db = testing_session_local()
    try:
        seeded = _seed_session(db, user_key='__demo__')
        seeded_id = seeded.id
    finally:
        db.close()

    response = client.patch(
        f'/api/resume-copilot/sessions/{seeded_id}',
        json={'name': 'attempted rename'},
        headers={'X-Resume-User-Key': 'anybody'},
    )
    assert response.status_code == 403
    assert response.json() == {'detail': 'Demo session is read-only'}


def test_cross_user_cannot_read_parsed_profile():
    client, testing_session_local = _build_test_client()

    db = testing_session_local()
    try:
        seeded = _seed_session(db, user_key='owner-A')
        db.add(ResumeParsedProfile(
            session_id=seeded.id,
            profile_json='{"basic_info":{"name":"Owner A","email":"a@a.com"}}',
        ))
        db.commit()
        seeded_id = seeded.id
    finally:
        db.close()

    response = client.get(
        f'/api/resume-copilot/sessions/{seeded_id}/parsed-profile',
        headers={'X-Resume-User-Key': 'owner-B'},
    )
    assert response.status_code == 403


def test_cross_user_cannot_delete_session():
    client, testing_session_local = _build_test_client()

    db = testing_session_local()
    try:
        seeded = _seed_session(db, user_key='owner-A')
        seeded_id = seeded.id
    finally:
        db.close()

    response = client.delete(
        f'/api/resume-copilot/sessions/{seeded_id}',
        headers={'X-Resume-User-Key': 'attacker'},
    )
    assert response.status_code == 403

    db = testing_session_local()
    try:
        still_there = db.query(ResumeCopilotSession).filter(
            ResumeCopilotSession.id == seeded_id
        ).first()
        assert still_there is not None
    finally:
        db.close()


# ─── C2: PII redaction ───────────────────────────────────────────────────────


def test_redact_profile_for_llm_strips_contact_fields():
    from app.schemas_resume_copilot import ResumeProfilePayload
    from app.services.resume_copilot.redact import redact_profile_for_llm

    profile = ResumeProfilePayload(
        basic_info={
            'name': '张三',
            'email': 'a@b.com',
            'phone': '13800138000',
            'github': 'gh.com/zs',
            'wechat': 'zs_wx',
            'qq': '12345',
            'address': '北京市',
            'school': '清华大学',  # not PII — should survive
        },
        candidate_summary='Backend candidate',
    )

    redacted = redact_profile_for_llm(profile)
    assert redacted.basic_info == {'school': '清华大学'}
    # Original is untouched (model_copy semantics)
    assert profile.basic_info['email'] == 'a@b.com'
    # Other fields preserved
    assert redacted.candidate_summary == 'Backend candidate'


def test_redact_profile_for_llm_handles_empty_basic_info():
    from app.schemas_resume_copilot import ResumeProfilePayload
    from app.services.resume_copilot.redact import redact_profile_for_llm

    profile = ResumeProfilePayload(basic_info={})
    assert redact_profile_for_llm(profile).basic_info == {}


def test_redact_profile_for_llm_is_case_insensitive():
    from app.schemas_resume_copilot import ResumeProfilePayload
    from app.services.resume_copilot.redact import redact_profile_for_llm

    profile = ResumeProfilePayload(basic_info={
        'Email': 'a@b.com',
        'PHONE': '13800',
        ' Mobile ': '139',
        'Major': 'CS',  # keep
    })
    out = redact_profile_for_llm(profile)
    assert 'Email' not in out.basic_info
    assert 'PHONE' not in out.basic_info
    assert ' Mobile ' not in out.basic_info
    assert out.basic_info == {'Major': 'CS'}


# ─── Q4: state machine + inflight guard ──────────────────────────────────────


def test_state_strenum_compares_equal_to_string():
    from app.services.resume_copilot.state import RunStatus, SessionStatus

    assert SessionStatus.COMPLETED == 'completed'
    assert RunStatus.RUNNING == 'running'
    # Round-trip through DB-style string assignment still matches
    db_value = 'failed'
    assert RunStatus.FAILED.value == db_value


def test_generate_rejects_409_when_recommendation_run_already_running():
    from datetime import datetime
    client, testing_session_local = _build_test_client()

    db = testing_session_local()
    try:
        seeded = _seed_session(db, user_key='test-user-key', status='awaiting_user_confirmation')
        seeded_id = seeded.id
        # Confirmed profile is required for /generate
        db.add(ResumeConfirmedProfile(
            session_id=seeded_id,
            profile_json='{"basic_info":{"name":"x"}}',
        ))
        # An already-running recommendation_run with a recent heartbeat
        db.add(ResumeRecommendationRun(
            session_id=seeded_id,
            status='running',
            updated_at=datetime.utcnow(),
        ))
        db.commit()
    finally:
        db.close()

    response = client.post(f'/api/resume-copilot/sessions/{seeded_id}/generate')
    assert response.status_code == 409
    assert response.json() == {'detail': 'GENERATE_ALREADY_RUNNING'}


def test_generate_recovers_when_running_run_is_stale(monkeypatch):
    from datetime import datetime, timedelta
    client, testing_session_local = _build_test_client()

    db = testing_session_local()
    try:
        seeded = _seed_session(db, user_key='test-user-key', status='awaiting_user_confirmation')
        seeded_id = seeded.id
        db.add(ResumeConfirmedProfile(
            session_id=seeded_id,
            profile_json='{"basic_info":{"name":"x"}}',
        ))
        # Running but heartbeat is 10 minutes old → considered stale
        db.add(ResumeRecommendationRun(
            session_id=seeded_id,
            status='running',
            updated_at=datetime.utcnow() - timedelta(minutes=10),
        ))
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr(
        'app.routers.resume_copilot.run_resume_generate_workflow',
        lambda _sid: None,
    )
    response = client.post(f'/api/resume-copilot/sessions/{seeded_id}/generate')
    assert response.status_code == 202
    assert response.json() == {'session_id': seeded_id, 'status': 'running'}


# ─── Q5: LLM JSON validation hardening ───────────────────────────────────────


def test_feedback_skips_malformed_diagnostics_keeps_valid():
    from app.schemas_resume_copilot import ResumeProfilePayload
    from app.services.resume_copilot.feedback import generate_feedback_for_profile

    class _MixedProvider:
        def generate_feedback(self, _profile, _prefs, _recs):
            return {
                'diagnostics': [
                    {'title': 'good', 'description': 'ok'},
                    {'wrong_shape': 'bad'},  # missing required fields
                    {'title': 'second good', 'description': 'still ok'},
                ],
                'rewrite_examples': [],
            }

    profile = ResumeProfilePayload(basic_info={'name': 'x'})
    diags, rewrites = generate_feedback_for_profile(profile, None, [], provider=_MixedProvider())

    assert len(diags) == 2
    assert [d.title for d in diags] == ['good', 'second good']
    assert rewrites == []


def test_feedback_returns_empty_on_non_dict_response():
    from app.schemas_resume_copilot import ResumeProfilePayload
    from app.services.resume_copilot.feedback import generate_feedback_for_profile

    class _BrokenProvider:
        def generate_feedback(self, _profile, _prefs, _recs):
            return [1, 2, 3]  # not a dict

    profile = ResumeProfilePayload(basic_info={'name': 'x'})
    diags, rewrites = generate_feedback_for_profile(profile, None, [], provider=_BrokenProvider())

    assert diags == []
    assert rewrites == []


def test_feedback_returns_empty_on_non_json_string():
    from app.schemas_resume_copilot import ResumeProfilePayload
    from app.services.resume_copilot.feedback import generate_feedback_for_profile

    class _StringProvider:
        def generate_feedback(self, _profile, _prefs, _recs):
            return 'this is not json'

    profile = ResumeProfilePayload(basic_info={'name': 'x'})
    diags, rewrites = generate_feedback_for_profile(profile, None, [], provider=_StringProvider())

    assert diags == []
    assert rewrites == []


def test_chat_falls_back_when_provider_returns_non_dict():
    """Chat workflow must keep the conversation alive on malformed LLM output."""
    from app.services.resume_copilot.chat import generate_chat_turn

    client, testing_session_local = _build_test_client()
    db = testing_session_local()
    try:
        seeded = _seed_session(db, user_key='test-user-key', status='completed')
        seeded_id = seeded.id
        db.add(ResumeConfirmedProfile(
            session_id=seeded_id,
            profile_json='{"basic_info":{"name":"x"},"internships":[],"projects":[],"candidate_summary":""}',
        ))
        db.commit()
    finally:
        db.close()

    class _MalformedChatProvider:
        def generate_turn(self, _payload):
            return ['not', 'a', 'dict']

    db = testing_session_local()
    try:
        result = generate_chat_turn(
            seeded_id, 'hello', db, provider=_MalformedChatProvider()
        )
    finally:
        db.close()

    # Workflow must NOT crash; user gets a graceful fallback message.
    assert result.role == 'assistant'
    assert result.content  # non-empty fallback
    assert result.rewrite_options is None
