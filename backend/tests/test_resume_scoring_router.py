"""B1 打分接口 — POST /sessions/{id}/score (provider 注入,不联网)。"""
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import ResumeConfirmedProfile, ResumeCopilotSession


class _FakeScorer:
    def score(self, messages_payload):
        return {
            'dimensions': [
                {'key': k, 'score': 70, 'ceiling': 80, 'reason': ''}
                for k in ['logic', 'star', 'readability', 'completeness',
                          'expression', 'quantification', 'track_fit', 'defensibility']
            ],
            'section_gaps': [{'section': 'internships.0', 'label': '九坤', 'gaps': ['缺 Result']}],
        }


def _build_client(monkeypatch, user_key='real_user_alpha'):
    from app.routers import resume_copilot
    from app.services.resume_copilot import scoring as scoring_mod

    monkeypatch.setattr(scoring_mod, 'OpenAICompatibleResumeScorer', lambda *a, **k: _FakeScorer())

    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    app = FastAPI()
    app.include_router(resume_copilot.router)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    client.headers.update({'X-Resume-User-Key': user_key})
    return client, SessionLocal


def _seed_session(SessionLocal, user_key, profile=None):
    db = SessionLocal()
    s = ResumeCopilotSession(file_name='cv.pdf', user_key=user_key, status='completed')
    db.add(s)
    db.commit()
    db.refresh(s)
    sid = int(s.id)
    if profile is not None:
        db.add(ResumeConfirmedProfile(session_id=sid, profile_json=json.dumps(profile)))
        db.commit()
    db.close()
    return sid


def test_score_endpoint_returns_report(monkeypatch):
    client, SessionLocal = _build_client(monkeypatch)
    sid = _seed_session(SessionLocal, 'real_user_alpha', profile={
        'inferred_tracks': ['量化'],
        'internships': [{'company': '九坤', 'bullets': ['参与因子开发']}],
    })
    resp = client.post(f'/api/resume-copilot/sessions/{sid}/score', json={'target_track': ''})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data['target_track'] == '量化'          # 空 → 自动推导
    assert data['overall_current'] == 70
    assert len(data['dimensions']) == 8
    assert data['section_gaps'][0]['label'] == '九坤'


def test_score_endpoint_404_without_profile(monkeypatch):
    client, SessionLocal = _build_client(monkeypatch)
    sid = _seed_session(SessionLocal, 'real_user_alpha', profile=None)
    resp = client.post(f'/api/resume-copilot/sessions/{sid}/score', json={})
    assert resp.status_code == 404


def test_score_endpoint_owner_guard(monkeypatch):
    client, SessionLocal = _build_client(monkeypatch, user_key='owner_a')
    sid = _seed_session(SessionLocal, 'owner_a', profile={'inferred_tracks': ['量化']})
    resp = client.post(
        f'/api/resume-copilot/sessions/{sid}/score',
        json={}, headers={'X-Resume-User-Key': 'someone_else'},
    )
    assert resp.status_code == 403
