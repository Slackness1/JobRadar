"""E2.5 深度优化写回:finalized draft → profile 段落。TDD(纯函数 + 端点)。"""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import ResumeConfirmedProfile, ResumeCopilotSession
from app.services.resume_copilot.deep_optimize import seed_plan_from_gap, write_back_current_draft
from app.services.resume_copilot.plan import Draft, ItemStatus
from app.schemas_resume_copilot import ResumeInternshipItem, ResumeProfilePayload

DRAFT = '搭建覆盖 40+ 量价因子的回测框架(2021–2023),将单因子筛选由手动改为一键批量,迭代周期缩短约 60%。'


def _plan_with_draft(section='internships.0'):
    plan = seed_plan_from_gap(section, '九坤投资 · 量化研究实习', ['STAR 缺 Result'], '缺最终结果', '量化')
    item = plan.items[0]
    item.status = ItemStatus.AWAITING_REVIEW
    item.draft = Draft(text=DRAFT)
    return plan


def test_write_back_replaces_section_bullets():
    plan = _plan_with_draft('internships.0')
    profile = ResumeProfilePayload(internships=[ResumeInternshipItem(bullets=['协助搭建因子回测框架'])])
    new_plan, out, section = write_back_current_draft(plan, profile)
    assert section == 'internships.0'
    assert out.internships[0].bullets == [DRAFT]
    assert new_plan.items[0].status == ItemStatus.FINALIZED
    # 原 profile 未被原地改(纯函数)
    assert profile.internships[0].bullets == ['协助搭建因子回测框架']


def test_write_back_no_draft_raises():
    plan = seed_plan_from_gap('internships.0', 'x', [], '', '量化')  # CLARIFYING, 无 draft
    with pytest.raises(ValueError):
        write_back_current_draft(plan, ResumeProfilePayload())


# ── 端点 ────────────────────────────────────────────────────────────────
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


def _seed(SessionLocal, user_key, plan=None):
    db = SessionLocal()
    s = ResumeCopilotSession(file_name='cv.pdf', user_key=user_key, status='completed')
    if plan is not None:
        s.plan_json = plan.model_dump_json()
        s.plan_status = plan.status.value
    db.add(s); db.commit(); db.refresh(s)
    sid = int(s.id)
    profile = ResumeProfilePayload(internships=[ResumeInternshipItem(bullets=['协助搭建因子回测框架'])])
    db.add(ResumeConfirmedProfile(session_id=sid, profile_json=profile.model_dump_json()))
    db.commit(); db.close()
    return sid


def test_write_back_endpoint_updates_profile():
    client, SessionLocal = _build_client('real_user_alpha')
    sid = _seed(SessionLocal, 'real_user_alpha', plan=_plan_with_draft('internships.0'))
    r = client.post(f'/api/resume-copilot/sessions/{sid}/deep-optimize/write-back', json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body['applied'] is True
    assert body['section'] == 'internships.0'
    assert body['profile']['internships'][0]['bullets'] == [DRAFT]
    # 落库
    db = SessionLocal()
    cp = db.query(ResumeConfirmedProfile).filter_by(session_id=sid).first()
    assert DRAFT in cp.profile_json
    db.close()


def test_write_back_endpoint_blocks_demo():
    client, SessionLocal = _build_client('__demo__')
    sid = _seed(SessionLocal, '__demo__', plan=_plan_with_draft())
    r = client.post(f'/api/resume-copilot/sessions/{sid}/deep-optimize/write-back', json={})
    assert r.status_code == 403


def test_write_back_endpoint_no_draft_400():
    client, SessionLocal = _build_client('real_user_alpha')
    sid = _seed(SessionLocal, 'real_user_alpha', plan=seed_plan_from_gap('internships.0', 'x', [], '', '量化'))
    r = client.post(f'/api/resume-copilot/sessions/{sid}/deep-optimize/write-back', json={})
    assert r.status_code == 400
