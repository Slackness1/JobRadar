"""B-深度优化 start 接口 — POST /sessions/{id}/deep-optimize/start。自建 in-memory client。"""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import ResumeCopilotSession


def _build_client(user_key='real_user_alpha'):
    from app.routers import resume_copilot

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


def _seed(SessionLocal, user_key):
    db = SessionLocal()
    s = ResumeCopilotSession(file_name='cv.pdf', user_key=user_key, status='completed')
    db.add(s); db.commit(); db.refresh(s)
    sid = int(s.id); db.close()
    return sid


def test_deep_optimize_start_seeds_focused_plan():
    client, SessionLocal = _build_client(user_key='real_user_alpha')
    sid = _seed(SessionLocal, 'real_user_alpha')
    r = client.post(f'/api/resume-copilot/sessions/{sid}/deep-optimize/start', json={
        'section': 'internships.0', 'label': '九坤投资 · 量化研究实习',
        'gaps': ['STAR 缺 Result'], 'detail': '协助搭建因子回测框架缺最终结果',
        'target_track': '量化',
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body['items']) == 1
    item = body['items'][0]
    assert item['kind'] == 'internship'
    assert item['title'] == '九坤投资 · 量化研究实习'
    assert item['status'] == 'clarifying'
    # 有缺口时首问从缺口开问(STAR 缺 Result → 问最终结果),不再问赛道
    assert 'STAR 缺 Result' in item['open_questions'][0]['text']
    assert body['status'] == 'clarifying'

    # 持久化: plan_json 落到 session
    db = SessionLocal()
    s = db.query(ResumeCopilotSession).get(sid)
    assert s.plan_json and '九坤' in s.plan_json
    assert s.plan_status == 'clarifying'
    db.close()


def test_deep_optimize_start_blocks_demo():
    client, SessionLocal = _build_client(user_key='__demo__')
    sid = _seed(SessionLocal, '__demo__')
    r = client.post(f'/api/resume-copilot/sessions/{sid}/deep-optimize/start', json={
        'section': 'internships.0', 'label': 'x', 'gaps': [], 'detail': '', 'target_track': '量化',
    })
    assert r.status_code == 403


def test_deep_optimize_start_wrong_owner_blocked():
    client, SessionLocal = _build_client(user_key='intruder')
    sid = _seed(SessionLocal, 'real_owner')
    r = client.post(f'/api/resume-copilot/sessions/{sid}/deep-optimize/start', json={
        'section': 'projects.0', 'label': 'x', 'gaps': [], 'detail': '', 'target_track': '',
    })
    assert r.status_code == 403
