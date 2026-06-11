"""简历编辑器草稿跨设备持久化端点 — GET/PUT 往返 + owner/demo 守卫。"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import ResumeCopilotSession


def _client():
    from app.routers import resume_copilot

    engine = create_engine(
        'sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool,
    )
    sl = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    app = FastAPI()
    app.include_router(resume_copilot.router)

    def override_get_db():
        db = sl()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.headers.update({'X-Resume-User-Key': 'owner-key'})
    return c, sl


def _seed(db: Session, **ov) -> ResumeCopilotSession:
    s = ResumeCopilotSession(file_name='r.pdf', user_key=ov.get('user_key', 'owner-key'))
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


_DRAFT = {
    'profile': {'name': '林思远', 'sections': []},
    'template': 'classic',
    'layout': {'cols': 1},
    'hidden': ['honor'],
}


def test_editor_draft_round_trip():
    c, sl = _client()
    db = sl()
    sid = _seed(db).id
    db.close()

    # 初始无草稿
    r0 = c.get(f'/api/resume-copilot/sessions/{sid}/editor-draft')
    assert r0.status_code == 200 and r0.json()['draft'] is None

    # PUT 落库
    rput = c.put(f'/api/resume-copilot/sessions/{sid}/editor-draft', json={'draft': _DRAFT})
    assert rput.status_code == 200 and rput.json()['ok'] is True

    # GET 取回(模拟换设备)
    r1 = c.get(f'/api/resume-copilot/sessions/{sid}/editor-draft')
    assert r1.status_code == 200
    assert r1.json()['draft'] == _DRAFT


def test_editor_draft_rejects_non_owner():
    c, sl = _client()
    db = sl()
    sid = _seed(db, user_key='someone-else').id
    db.close()
    # owner-key 不是该会话主人 → 403
    r = c.put(f'/api/resume-copilot/sessions/{sid}/editor-draft', json={'draft': _DRAFT})
    assert r.status_code == 403


def test_editor_draft_put_blocks_demo():
    c, sl = _client()
    db = sl()
    sid = _seed(db, user_key='__demo__').id
    db.close()
    # demo 只读 —— 但 owner 守卫先于 demo 守卫: owner-key != __demo__ → 先 403。
    # 用 demo key 当 owner 才会走到 demo 守卫。
    c.headers.update({'X-Resume-User-Key': '__demo__'})
    r = c.put(f'/api/resume-copilot/sessions/{sid}/editor-draft', json={'draft': _DRAFT})
    assert r.status_code == 403
